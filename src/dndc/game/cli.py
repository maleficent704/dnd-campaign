"""`dndc` entry point.

Phase 0's command surface: `srd` (P0.2) and `new-campaign` / `roll` / `sheet` (P0.5).
The play loop itself arrives in Phase 1.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from pydantic import ValidationError
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from dndc import __version__
from dndc.config import Billing, load_config, load_env_file, save_billing_default
from dndc.game.campaign import (
    CampaignError,
    campaign_dir,
    create_campaign,
    list_campaigns,
    load_campaign,
)
from dndc.game.creation import (
    CreationSession,
    load_campaign_canon,
    load_campaign_sheets,
    summarize,
)
from dndc.game.turn import TurnEngine
from dndc.gm import (
    DEFAULT_WINDOW,
    SCAFFOLDING_TEMPLATES,
    CampaignContext,
    CanonLedger,
    CreationPromptBuilder,
    GMPromptBuilder,
    PartyMember,
)
from dndc.logging import SessionLog, git_commit_sha, resolve_log_dir
from dndc.models import (
    THROTTLE_WARNING,
    GMBackendError,
    build_gm_backend,
    estimate_cost,
    load_prices,
)
from dndc.rules.build import BuildError, grant_issues
from dndc.rules.dice import Advantage, DiceError, roll, roll_d20
from dndc.schema.events import Cost, DiceRoll, GMNarration, RulesResolution, SeatInfo, SessionMeta
from dndc.schema.sheet import SKILL_ABILITY, Ability, CharacterSheet, Skill
from dndc.schema.srd import IngestScope
from dndc.srd import SRDIngestError, ingest, load_dataset, validate_dataset, verify_pin
from dndc.srd.repository import SRDRepository

MAX_SEED = 2**32


def _seats_for_meta(cfg) -> dict[str, SeatInfo]:
    """Snapshot the resolved seats so a log says what actually ran."""
    return {
        "gm": SeatInfo(backend=cfg.seats.gm.backend, model=cfg.seats.gm.model_default),
        "npc": SeatInfo(
            backend=cfg.seats.npc.backend,
            model=cfg.seats.npc.model,
            endpoint=cfg.seats.npc.endpoint,
        ),
        "utility": SeatInfo(
            backend=cfg.seats.utility.backend,
            model=cfg.seats.utility.model,
            endpoint=cfg.seats.utility.endpoint,
        ),
    }


def start_session_log(
    cfg,
    campaign: str | None = None,
    seed: int | None = None,
    billing: Billing | None = None,
) -> SessionLog:
    """Open a session log and write its `session_meta` header (D-008)."""
    log = SessionLog.open(resolve_log_dir(cfg.logging.dir))
    sha, dirty = git_commit_sha() if cfg.logging.stamp_commit_sha else (None, False)
    log.emit(
        SessionMeta,
        dndc_version=__version__,
        commit_sha=sha,
        dirty_worktree=dirty,
        billing=(billing or cfg.billing.default).value,
        campaign=campaign,
        seats=_seats_for_meta(cfg),
        gameplay={
            "scaffolding": cfg.gameplay.scaffolding,
            "play_mode": cfg.gameplay.play_mode,
        },
        seed=seed,
    )
    return log


def resolve_billing(
    cfg,
    console: Console,
    requested: str | None = None,
    ask: bool = True,
    remember: bool = True,
) -> Billing:
    """Settle the billing path for this session (D-004).

    `--billing` wins; otherwise ask, defaulting to the sticky value from config. The
    answer becomes the new default, because household usage varies week to week and the
    last choice is the best guess at the next one.
    """
    if requested is not None:
        choice = Billing(requested)
    elif ask and sys.stdin.isatty():
        default = cfg.billing.default
        console.print(
            f"[bold]billing[/bold] — [cyan]api[/cyan] (metered, spend-capped) or "
            f"[cyan]subscription[/cyan] (weekly Max pool)"
        )
        answer = Prompt.ask("  mode", choices=[b.value for b in Billing], default=default.value)
        choice = Billing(answer)
    else:
        choice = cfg.billing.default

    if choice is Billing.SUBSCRIPTION:
        console.print(f"[yellow]heads-up:[/yellow] {THROTTLE_WARNING}")

    if remember and choice is not cfg.billing.default and save_billing_default(choice):
        console.print(f"[dim]sticky default is now {choice.value}[/dim]")
    return choice


# --- config ----------------------------------------------------------------


def _cmd_check_config(console: Console) -> int:
    cfg = load_config()
    console.print(f"[bold]billing default:[/bold] {cfg.billing.default.value}")
    console.print(f"[bold]gm:[/bold] {cfg.seats.gm.model_default} "
                  f"(threshold: {cfg.seats.gm.model_threshold})")
    console.print(f"[bold]npc:[/bold] {cfg.seats.npc.model} @ {cfg.seats.npc.endpoint}")
    console.print(f"[bold]utility:[/bold] {cfg.seats.utility.model} @ {cfg.seats.utility.endpoint}")
    return 0


# --- srd -------------------------------------------------------------------


def _cmd_srd_ingest(console: Console, args: argparse.Namespace) -> int:
    scope = IngestScope(
        max_class_level=args.max_class_level, max_challenge_rating=args.max_cr
    )
    report = ingest(scope=scope)
    console.print(
        f"[green]ingested[/green] -> {report.output_root} "
        f"(classes L1-{scope.max_class_level}, monsters CR 0-{scope.max_challenge_rating:g})"
    )
    for collection, count in report.counts.items():
        console.print(f"  {collection:<12} {count}")
    if report.issues:
        console.print(f"[yellow]{len(report.issues)} validation issue(s):[/yellow]")
        for issue in report.issues[:20]:
            console.print(f"  - {issue}")
        return 1
    return 0


def _cmd_srd_stats(console: Console) -> int:
    data = load_dataset()
    table = Table(title="SRD 5.1 (2014) — normalized", title_style="bold")
    table.add_column("collection")
    table.add_column("count", justify="right")
    for collection, count in data.counts().items():
        table.add_row(collection, str(count))
    console.print(table)

    by_cr: dict[float, int] = {}
    for monster in data.monsters.values():
        by_cr[monster.challenge_rating] = by_cr.get(monster.challenge_rating, 0) + 1
    console.print(
        "[bold]monsters by CR:[/bold] "
        + "  ".join(f"{cr:g}:{n}" for cr, n in sorted(by_cr.items()))
    )

    casters = [c for c in data.classes.values() if c.spellcasting_ability]
    console.print(
        f"[bold]classes:[/bold] {len(data.classes)} "
        f"({len(casters)} spellcasting) — levels 1-{data.scope.max_class_level}"
    )
    cantrips = sum(1 for s in data.spells.values() if s.is_cantrip)
    console.print(f"[bold]spells:[/bold] {len(data.spells)} ({cantrips} cantrips)")
    return 0


def _cmd_srd_verify(console: Console) -> int:
    problems = verify_pin()
    if problems:
        console.print(f"[red]pin verification FAILED[/red] ({len(problems)} problem(s)):")
        for problem in problems:
            console.print(f"  - {problem}")
        return 1
    console.print("[green]pin OK[/green] — vendored raw data matches SOURCE.json")

    try:
        data = load_dataset()
    except SRDIngestError as exc:
        console.print(f"[yellow]no normalized dataset:[/yellow] {exc}")
        return 1
    issues = validate_dataset(data)
    if issues:
        console.print(f"[red]{len(issues)} validation issue(s):[/red]")
        for issue in issues[:20]:
            console.print(f"  - {issue}")
        return 1
    console.print("[green]dataset OK[/green] — referential integrity and dice expressions")
    return 0


# --- campaigns -------------------------------------------------------------


def _cmd_new_campaign(console: Console, args: argparse.Namespace) -> int:
    cfg = load_config()
    try:
        campaign = create_campaign(
            args.name,
            players=args.player or [],
            scaffolding=args.scaffolding or cfg.gameplay.scaffolding,
            play_mode=cfg.gameplay.play_mode,
        )
    except (CampaignError, ValueError) as exc:
        console.print(f"[red]error:[/red] {exc}")
        return 1

    target = campaign_dir(campaign.slug)
    console.print(f"[green]created[/green] campaign [bold]{campaign.name}[/bold] -> {target}")
    console.print(f"  scaffolding: {campaign.scaffolding}   play mode: {campaign.play_mode}")
    if campaign.players:
        console.print(f"  players: {', '.join(campaign.players)}")
    console.print(
        f"  next: [bold]dndc create-character --campaign {campaign.slug} --player NAME[/bold]"
    )
    return 0


def _cmd_campaigns(console: Console) -> int:
    campaigns = list_campaigns()
    if not campaigns:
        console.print("no campaigns yet — `dndc new-campaign \"Name\"`")
        return 0
    table = Table(title="campaigns", title_style="bold")
    for column in ("name", "slug", "created", "players"):
        table.add_column(column)
    for campaign in campaigns:
        table.add_row(
            campaign.name, campaign.slug, str(campaign.created), ", ".join(campaign.players)
        )
    console.print(table)
    return 0


# --- roll ------------------------------------------------------------------


def _cmd_roll(console: Console, args: argparse.Namespace) -> int:
    # Always resolve a seed, even when the user did not give one: an unrecorded roll is
    # not reproducible, and reproducibility is the point of the deterministic core.
    seed = args.seed if args.seed is not None else random.randrange(MAX_SEED)
    rng = random.Random(seed)

    advantage = Advantage.NORMAL
    if args.advantage:
        advantage = Advantage.ADVANTAGE
    elif args.disadvantage:
        advantage = Advantage.DISADVANTAGE

    try:
        if args.expression.strip().casefold() in {"d20", "1d20"} or advantage is not Advantage.NORMAL:
            result = roll_d20(rng, modifier=args.modifier, advantage=advantage)
            rolls, kept = result.rolls, (result.natural,)
            total, expression = result.total, "1d20"
            # On advantage/disadvantage both faces matter — showing only the kept one
            # hides exactly what the player wants to see.
            detail = (
                f"rolls {list(result.rolls)} -> natural {result.natural}"
                if len(result.rolls) > 1
                else f"natural {result.natural}"
            )
            if result.is_natural_20:
                detail += " [bold green](nat 20)[/bold green]"
            elif result.is_natural_1:
                detail += " [bold red](nat 1)[/bold red]"
            modifier = args.modifier
        else:
            outcome = roll(args.expression, rng)
            rolls = outcome.all_rolls
            kept = tuple(k for group in outcome.groups for k in group.kept)
            total, expression = outcome.total + args.modifier, outcome.expression
            modifier = args.modifier
            detail = f"rolls {list(rolls)}"
    except DiceError as exc:
        console.print(f"[red]error:[/red] {exc}")
        return 1

    label = expression + (f" {modifier:+d}" if modifier else "")
    console.print(f"[bold]{label}[/bold] = [bold cyan]{total}[/bold cyan]   {detail}")
    console.print(f"[dim]seed {seed}  ({advantage.value})[/dim]")

    if args.log:
        cfg = load_config()
        log = start_session_log(cfg, seed=seed)
        log.emit(
            RulesResolution,
            kind="roll",
            advantage=advantage.value,
            seed=seed,
            roll=DiceRoll(
                expression=expression,
                rolls=tuple(rolls),
                kept=tuple(kept),
                modifier=modifier,
                total=total,
            ),
        )
        console.print(f"[dim]logged -> {log.path}[/dim]")
    return 0


# --- gm --------------------------------------------------------------------

def _gm_campaign_context(
    console: Console, args: argparse.Namespace
) -> tuple[CampaignContext, dict[str, CharacterSheet]] | None:
    """Assemble what the builder needs, plus the sheets the engine resolves against.

    The party summary in the prompt is deliberately thin (the GM narrates; it does not
    need a proficiency table), but a check has to resolve against the real scores — so
    both come back and stay separate.

    `--campaign` reads a real campaign directory: its name, the characters co-creation
    wrote, and its canon ledger. `--character` still works and stacks on top, which is
    what keeps a scratch sheet runnable without creating a campaign for it.
    """
    slug = getattr(args, "campaign", None)
    campaign = CampaignContext(name=args.campaign_name or "Untitled campaign")
    sheets: dict[str, CharacterSheet] = {}

    if slug:
        try:
            record = load_campaign(slug)
        except (CampaignError, ValidationError) as exc:
            console.print(f"[red]error:[/red] {exc}")
            return None
        campaign.name = args.campaign_name or record.name
        campaign.ledger = load_campaign_canon(slug)
        for sheet in load_campaign_sheets(slug):
            campaign.party.append(PartyMember.from_sheet(sheet))
            sheets[sheet.name.lower()] = sheet

    campaign.scene = args.scene or ""
    if args.canon:
        campaign.ledger = CanonLedger.load(args.canon)

    for path in args.character or ():
        sheet = _load_sheet(console, path)
        if sheet is None:
            return None
        if sheet.name.lower() in sheets:
            continue
        campaign.party.append(PartyMember.from_sheet(sheet))
        sheets[sheet.name.lower()] = sheet
    return campaign, sheets


def _cmd_gm(console: Console, args: argparse.Namespace) -> int:
    """One narration turn against the real prompt assembly (P1.2)."""
    cfg = load_config()
    scaffolding = args.scaffolding or cfg.gameplay.scaffolding
    builder = GMPromptBuilder(scaffolding=scaffolding)
    loaded = _gm_campaign_context(console, args)
    if loaded is None:
        return 1
    campaign, _sheets = loaded
    request = builder.build(
        campaign,
        player_input=args.prompt,
        resolutions=tuple(args.resolution or ()),
        max_tokens=args.max_tokens,
    )

    # Before any billing prompt or backend construction: inspecting the prompt must not
    # need a key, a login, or a decision about who pays.
    if args.show_prompt:
        for heading, body in (
            ("system (cached prefix)", request.system),
            ("campaign state (volatile)", request.system_volatile),
        ):
            console.print(f"[dim]--- {heading} ---[/dim]")
            console.print(body, markup=False, highlight=False, soft_wrap=True)
        console.print("[dim]--- messages ---[/dim]")
        for message in request.messages:
            console.print(f"[dim]{message.role.value}:[/dim]")
            console.print(message.content, markup=False, highlight=False, soft_wrap=True)
        return 0

    billing = resolve_billing(cfg, console, requested=args.billing, ask=not args.no_prompt)
    try:
        backend = build_gm_backend(cfg, billing, threshold=args.threshold)
    except GMBackendError as exc:
        console.print(f"[red]error:[/red] {exc}")
        return 1

    log = start_session_log(cfg, seed=None, billing=billing) if args.log else None
    console.print(f"[dim]{backend.name} · {request.model or cfg.seats.gm.model_default}[/dim]")

    try:
        # markup=False: the GM's check-request form is `[[CHECK: ...]]`, which rich would
        # otherwise try to parse as a style tag and swallow.
        response = backend.generate(
            request,
            on_text=lambda chunk: console.print(chunk, end="", markup=False, highlight=False),
        )
    except GMBackendError as exc:
        console.print(f"\n[red]error:[/red] {exc}")
        return 1
    except Exception as exc:  # network / rate limit — retryable, surfaced as-is
        console.print(f"\n[red]call failed:[/red] {type(exc).__name__}: {exc}")
        return 1
    finally:
        backend.close()

    console.print()
    if response.refused:
        console.print(
            f"[yellow]the model declined this request[/yellow]"
            + (f" ({response.refusal_category})" if response.refusal_category else "")
        )

    usage = response.usage
    console.print(
        f"[dim]tokens in {usage.input_tokens} · out {usage.output_tokens} · "
        f"cache r{usage.cache_read_tokens}/w{usage.cache_write_tokens}"
        + (f" · {response.duration_ms}ms" if response.duration_ms else "")
        + "[/dim]"
    )

    prices = load_prices(cfg.pricing)
    estimated = estimate_cost(usage, response.model, prices)
    if billing is Billing.SUBSCRIPTION:
        # D-004: subscription spends the pool, not dollars — the dollar figure is what
        # the same call would have cost on the API, which is what makes the toggle
        # measurable rather than a matter of opinion.
        shown = response.reported_usd if response.reported_usd is not None else estimated
        if shown is not None:
            console.print(f"[dim]would have cost ${shown:.4f} at API rates[/dim]")
    elif estimated is not None:
        console.print(f"[dim]${estimated:.4f}[/dim]")

    if log is not None:
        log.emit(
            GMNarration,
            text=response.text,
            model=response.model,
            call_id=response.call_id,
            scaffolding=scaffolding,
        )
        log.emit(
            Cost,
            seat="gm",
            model=response.model,
            billing=billing.value,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            usd=response.reported_usd if response.reported_usd is not None else estimated,
            would_have_cost=billing is Billing.SUBSCRIPTION,
            call_id=response.call_id,
        )
        console.print(f"[dim]logged -> {log.path}[/dim]")
    return 0


# --- play ------------------------------------------------------------------

PLAY_HELP = """[bold]commands[/bold]
  /who            show the party and who is currently acting
  /switch <name>  hand the keyboard to another player
  /scene <text>   set where the party is
  /recap          replay the recent window
  /quit           end the session
anything else is what your character says or does."""


class _NarrationStream:
    """Streams GM text to the console with `[[...]]` machine tags held back.

    Tags are instructions to the engine, not prose. Streaming one raw put a literal
    `[[CHECK: Strength DC 15 ...]]` in front of the players mid-sentence. Text is held
    from the first `[` and released as soon as it cannot be the start of a tag, so
    ordinary bracketed prose still comes through.

    The filter is on `[[` rather than on each tag name: every tag the project has added
    since — `[[PROPOSE:`, `[[FACT:` — is the same kind of thing, and a filter that has to
    be updated per tag is one that will eventually miss one in front of a player.
    """

    _MARKER = "[["

    def __init__(self, console: Console) -> None:
        self.console = console
        self._held = ""
        self._suppressing = False
        self._swallow = False

    def feed(self, chunk: str) -> None:
        for char in chunk:
            if self._suppressing:
                self._held += char
                if self._held.endswith("]]"):
                    self._held = ""
                    self._suppressing = False
                    # Whatever whitespace followed the tag was there to space out the
                    # tag; the whitespace *before* it already went through, so keeping
                    # this too leaves a hole in the middle of the reply.
                    self._swallow = True
                continue

            if self._swallow:
                if char.isspace():
                    continue
                self._swallow = False

            if self._held or char == "[":
                self._held += char
                candidate = self._MARKER[: len(self._held)]
                if self._held.upper() == candidate:
                    if len(self._held) == len(self._MARKER):
                        self._suppressing = True
                    continue
                self._emit(self._held)
                self._held = ""
                continue

            self._emit(char)

    def finish(self) -> None:
        if self._held and not self._suppressing:
            self._emit(self._held)
        self._held = ""

    def _emit(self, text: str) -> None:
        self.console.print(text, end="", markup=False, highlight=False)


def _render_mechanics(console: Console, results) -> None:
    """OD-11: the numbers are rendered here, from state — never quoted by the GM."""
    if not results:
        return
    console.print()
    for result in results:
        colour = "green" if result.success else "red"
        console.print(f"  [{colour}]{result.render()}[/{colour}]")
        console.print(f"  [dim]seed {result.seed}[/dim]")


def _cmd_play(console: Console, args: argparse.Namespace) -> int:
    """The hot-seat turn loop (P1.3, OD-4)."""
    cfg = load_config()
    loaded = _gm_campaign_context(console, args)
    if loaded is None:
        return 1
    campaign, loaded_sheets = loaded
    if not campaign.party:
        console.print(
            "[yellow]no characters loaded[/yellow] — pass --campaign SLUG (after "
            "`dndc create-character`) or --character PATH."
        )
        return 1

    billing = resolve_billing(cfg, console, requested=args.billing, ask=not args.no_prompt)
    try:
        backend = build_gm_backend(cfg, billing, threshold=args.threshold)
    except GMBackendError as exc:
        console.print(f"[red]error:[/red] {exc}")
        return 1

    seed = args.seed if args.seed is not None else random.randrange(MAX_SEED)
    log = start_session_log(cfg, campaign=campaign.name, seed=seed, billing=billing)
    engine = TurnEngine(
        backend=backend,
        campaign=campaign,
        builder=GMPromptBuilder(scaffolding=args.scaffolding or cfg.gameplay.scaffolding),
        rng=random.Random(seed),
        log=log,
        max_tokens=args.max_tokens,
        billing=billing.value,
        prices=load_prices(cfg.pricing),
    )

    sheets = {member.name.lower(): member for member in campaign.party}
    active = campaign.party[0].name

    console.print(f"[bold]{campaign.name}[/bold] — {backend.name}, seed {seed}")
    console.print(f"[dim]log -> {log.path}  ·  /help for commands[/dim]\n")

    try:
        # The GM speaks first, as at a table. Without this the loop sat waiting for a
        # player who had not been told where they were standing (first playtest).
        if not campaign.history:
            stream = _NarrationStream(console)
            try:
                engine.open_scene(on_text=stream.feed)
            except GMBackendError as exc:
                console.print(f"[red]error:[/red] {exc}")
                return 1
            except Exception as exc:  # network / rate limit
                console.print(f"\n[red]call failed:[/red] {type(exc).__name__}: {exc}")
                return 1
            finally:
                stream.finish()
            console.print("\n")

        while True:
            member = sheets[active.lower()]
            try:
                raw = Prompt.ask(f"[bold cyan]{member.player} ({member.name})[/bold cyan]")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]session ended[/dim]")
                break

            text = raw.strip()
            if not text:
                continue
            if text.startswith("/"):
                if _play_command(console, text, campaign, sheets) == "quit":
                    break
                if text.split()[0] == "/switch":
                    target = text[len("/switch"):].strip().lower()
                    if target in sheets:
                        active = sheets[target].name
                continue

            console.print()
            stream = _NarrationStream(console)
            result = engine.run(
                text,
                player=member.player,
                sheet=loaded_sheets.get(active.lower()),
                on_text=stream.feed,
            )
            stream.finish()
            console.print()
            if result.refused:
                console.print("[yellow]the model declined that turn[/yellow]")
            _render_mechanics(console, result.mechanics)
            console.print()
    finally:
        backend.close()

    console.print(f"[dim]logged -> {log.path}[/dim]")
    return 0


def _play_command(console: Console, text: str, campaign, sheets) -> str | None:
    """Slash commands. Returns 'quit' to end the loop."""
    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else ""

    if command in {"/quit", "/exit"}:
        return "quit"
    if command == "/help":
        console.print(PLAY_HELP)
    elif command == "/who":
        for member in campaign.party:
            console.print(f"  {member.render()}")
    elif command == "/switch":
        if argument.lower() not in sheets:
            console.print(f"[yellow]no character called {argument!r}[/yellow]")
    elif command == "/scene":
        if argument:
            campaign.scene = argument
            console.print("[dim]scene set[/dim]")
        else:
            console.print(campaign.scene or "[dim](no scene set)[/dim]")
    elif command == "/recap":
        for turn in campaign.history[-DEFAULT_WINDOW:]:
            console.print(f"[dim]{turn.speaker}:[/dim] {turn.player_input}")
            console.print(turn.narration, markup=False, highlight=False, soft_wrap=True)
    else:
        console.print(f"[yellow]unknown command {command}[/yellow] — /help")
    return None


# --- create-character ------------------------------------------------------

CREATE_HELP = """[bold]commands[/bold]
  /sheet    show the character as it currently stands
  /done     save the character and the backstory canon, and finish
  /quit     leave without saving
anything else is you, talking to the GM."""


def _cmd_create_character(console: Console, args: argparse.Namespace) -> int:
    """Guided co-creation (P1.4, D-005). The conversation is the UX; the sheet is output."""
    cfg = load_config()
    try:
        repo = SRDRepository.load()
    except SRDIngestError as exc:
        console.print(f"[red]error:[/red] {exc}")
        return 1

    # Before the campaign lookup, the billing question, and the backend: inspecting the
    # prompt is a debugging tool and must not need a key, a login, or a campaign (P1.2).
    if args.show_prompt:
        console.print(
            CreationPromptBuilder(repo).system(),
            markup=False, highlight=False, soft_wrap=True,
        )
        return 0

    missing = [flag for flag, value in (("--campaign", args.campaign),
                                        ("--player", args.player)) if not value]
    if missing:
        console.print(f"[red]error:[/red] {' and '.join(missing)} are required to create")
        return 1

    try:
        campaign = load_campaign(args.campaign)
    except (CampaignError, ValidationError) as exc:
        console.print(f"[red]error:[/red] {exc}")
        return 1

    billing = resolve_billing(cfg, console, requested=args.billing, ask=not args.no_prompt)
    try:
        backend = build_gm_backend(cfg, billing, threshold=args.threshold)
    except GMBackendError as exc:
        console.print(f"[red]error:[/red] {exc}")
        return 1

    log = start_session_log(cfg, campaign=campaign.name, billing=billing)
    session = CreationSession(
        backend=backend,
        repo=repo,
        player=args.player,
        log=log,
        max_tokens=args.max_tokens,
        billing=billing.value,
        prices=load_prices(cfg.pricing),
    )

    console.print(f"[bold]{campaign.name}[/bold] — making a character for {args.player}")
    console.print(f"[dim]log -> {log.path}  ·  /help for commands[/dim]\n")

    saved = False
    try:
        _creation_reply(console, session.open(on_text=None), stream=False)
        while True:
            try:
                raw = Prompt.ask(f"[bold cyan]{args.player}[/bold cyan]")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]left without saving[/dim]")
                break

            text = raw.strip()
            if not text:
                continue

            if text.startswith("/"):
                command = text.split()[0].lower()
                if command in {"/quit", "/exit"}:
                    console.print("[dim]left without saving[/dim]")
                    break
                if command == "/help":
                    console.print(CREATE_HELP)
                elif command == "/sheet":
                    if session.sheet is None:
                        console.print("[dim]nothing built yet[/dim]")
                    else:
                        _render_sheet(console, session.sheet)
                elif command == "/done":
                    if session.sheet is None:
                        console.print(
                            "[yellow]no character built yet[/yellow] — keep talking, or "
                            "ask the GM to make one from what you have said."
                        )
                        continue
                    try:
                        sheet_path, canon_path = session.finish(campaign.slug)
                    except BuildError as exc:
                        console.print(f"[red]error:[/red] {exc}")
                        continue
                    saved = True
                    console.print(f"[green]saved[/green] {summarize(session.sheet, session.facts)}")
                    console.print(f"  sheet -> {sheet_path}")
                    console.print(f"  canon -> {canon_path}")
                    break
                else:
                    console.print(f"[yellow]unknown command {command}[/yellow] — /help")
                continue

            console.print()
            stream = _NarrationStream(console)
            try:
                reply = session.say(text, on_text=stream.feed)
            except GMBackendError as exc:
                console.print(f"\n[red]error:[/red] {exc}")
                break
            except Exception as exc:  # network / rate limit
                console.print(f"\n[red]call failed:[/red] {type(exc).__name__}: {exc}")
                break
            stream.finish()
            _creation_reply(console, reply, stream=True)
    finally:
        backend.close()

    if not saved and session.sheet is not None:
        console.print("[yellow]the built character was not saved[/yellow] (/done saves it)")
    console.print(f"[dim]logged -> {log.path}[/dim]")
    return 0


def _creation_reply(console: Console, reply, stream: bool) -> None:
    """Show one exchange. Already-streamed prose is not printed twice."""
    if not stream:
        console.print(reply.text, markup=False, highlight=False, soft_wrap=True)
    console.print()

    if reply.refused:
        console.print("[yellow]the model declined that[/yellow]")
    for fact in reply.facts:
        console.print(f"  [dim]canon:[/dim] {fact}")
    if reply.sheet is not None:
        console.print()
        _render_sheet(console, reply.sheet)
        console.print("[dim]/done to save, or keep talking to change it[/dim]")
    if reply.error:
        console.print(f"[red]the engine could not build that character:[/red] {reply.error}")
    console.print()


# --- sheet -----------------------------------------------------------------


def _load_sheet(console: Console, path: str) -> CharacterSheet | None:
    target = Path(path)
    if not target.exists():
        console.print(f"[red]error:[/red] no sheet at {target}")
        return None
    try:
        return CharacterSheet.load(target)
    except ValidationError as exc:
        console.print(f"[red]invalid sheet[/red] {target}:")
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "(root)"
            console.print(f"  - {location}: {error['msg']}")
        return None
    except Exception as exc:  # malformed YAML
        console.print(f"[red]could not read[/red] {target}: {exc}")
        return None


def _cmd_sheet_show(console: Console, args: argparse.Namespace) -> int:
    sheet = _load_sheet(console, args.path)
    if sheet is None:
        return 1
    _render_sheet(console, sheet)
    return 0


def _render_sheet(console: Console, sheet: CharacterSheet) -> None:
    """The authoritative display of a character. Co-creation shows this rather than
    letting the GM recite scores it may have got wrong (OD-11's principle, applied to
    the sheet: one place the numbers come from, and it is the engine)."""
    console.print(
        f"[bold]{sheet.name}[/bold] — level {sheet.level} {sheet.species} {sheet.character_class}"
        + (f"  ([dim]{sheet.player}[/dim])" if sheet.player else "")
    )
    console.print(
        f"AC [bold]{sheet.armor_class}[/bold]   "
        f"HP [bold]{sheet.hit_points.current}/{sheet.hit_points.maximum}[/bold]"
        + (f" (+{sheet.hit_points.temporary} temp)" if sheet.hit_points.temporary else "")
        + f"   speed {sheet.speed} ft   PB +{sheet.proficiency_bonus}   "
        f"init {sheet.initiative_modifier:+d}   passive perception {sheet.passive_perception}"
    )

    abilities = Table(show_header=True, header_style="bold")
    for column in ("ability", "score", "mod", "save"):
        abilities.add_column(column, justify="right")
    for ability in Ability:
        abilities.add_row(
            ability.value.upper(),
            str(sheet.abilities.score(ability)),
            f"{sheet.abilities.modifier(ability):+d}",
            f"{sheet.saving_throw_modifier(ability):+d}",
        )
    console.print(abilities)

    skills = Table(show_header=True, header_style="bold")
    for column in ("skill", "ability", "mod"):
        skills.add_column(column)
    for skill in Skill:
        level = sheet.proficiencies.skills.get(skill)
        name = skill.value.replace("_", " ").title()
        if level is not None and level.value != "none":
            name = f"[bold]{name}[/bold] ({level.value})"
        skills.add_row(name, SKILL_ABILITY[skill].value.upper(),
                       f"{sheet.skill_modifier(skill):+d}")
    console.print(skills)

    if sheet.inventory:
        console.print(f"[bold]inventory[/bold] ({sheet.carried_weight:g} lb)")
        for item in sheet.inventory:
            quantity = f" x{item.quantity}" if item.quantity > 1 else ""
            equipped = " [green](equipped)[/green]" if item.equipped else ""
            console.print(f"  - {item.name}{quantity}{equipped}")

    if sheet.spell_slots:
        slots = "  ".join(
            f"L{level}: {slot.available}/{slot.total}"
            for level, slot in sorted(sheet.spell_slots.items())
        )
        console.print(f"[bold]spell slots[/bold]  {slots}")


def _cmd_sheet_validate(console: Console, args: argparse.Namespace) -> int:
    sheet = _load_sheet(console, args.path)
    if sheet is None:
        return 1
    console.print(f"[green]valid[/green] — {sheet.name}, level {sheet.level} "
                  f"{sheet.species} {sheet.character_class}")

    # Schema-valid is not the same as complete: a sheet can parse cleanly and still be
    # missing what its species and class actually grant. That is how the first
    # co-created character reached the table two ability points short.
    try:
        issues = grant_issues(sheet, SRDRepository.load())
    except SRDIngestError as exc:
        console.print(f"[dim]grants not checked: {exc}[/dim]")
        return 0

    if issues:
        # A warning, not a failure: the sheet is a valid, loadable character, and sheets
        # are hand-editable data (D-005). Construction is where incompleteness is fatal
        # — `build_character` raises. Inspection reports.
        console.print(f"[yellow]{len(issues)} incomplete grant(s)[/yellow] — "
                      f"this character is missing things its species and class give it:")
        for issue in issues:
            console.print(f"  - {issue}")
        return 0
    console.print("[green]grants complete[/green] — matches SRD species and class")
    return 0


# --- parser ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dndc", description=__doc__)
    parser.add_argument("--version", action="version", version=f"dndc {__version__}")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate config.yaml and print the resolved model seats",
    )
    commands = parser.add_subparsers(dest="command")

    srd = commands.add_parser("srd", help="SRD reference data")
    srd_commands = srd.add_subparsers(dest="srd_command")
    srd_ingest = srd_commands.add_parser(
        "ingest", help="normalize the pinned raw SRD into data/srd/normalized/"
    )
    srd_ingest.add_argument(
        "--max-class-level", type=int, default=IngestScope().max_class_level,
        help="highest class level to ingest (default: %(default)s)",
    )
    srd_ingest.add_argument(
        "--max-cr", type=float, default=IngestScope().max_challenge_rating,
        help="highest monster challenge rating to ingest (default: %(default)s)",
    )
    srd_commands.add_parser("stats", help="summarize the normalized dataset")
    srd_commands.add_parser("verify", help="check the pin hashes and dataset integrity")

    new_campaign = commands.add_parser("new-campaign", help="create a campaign")
    new_campaign.add_argument("name")
    new_campaign.add_argument(
        "--player", action="append", metavar="NAME", help="repeatable"
    )
    new_campaign.add_argument(
        "--scaffolding", choices=["high", "low", "off"],
        help="D-006 option surfacing (default: from config.yaml)",
    )
    commands.add_parser("campaigns", help="list campaigns")

    roll_command = commands.add_parser("roll", help="roll dice through the rules engine")
    roll_command.add_argument("expression", help="e.g. 2d6+3, 4d6kh3, d20")
    roll_command.add_argument("--modifier", type=int, default=0)
    roll_command.add_argument("--advantage", action="store_true")
    roll_command.add_argument("--disadvantage", action="store_true")
    roll_command.add_argument(
        "--seed", type=int, help="reproduce an earlier roll (one is generated if omitted)"
    )
    roll_command.add_argument(
        "--log", action="store_true", help="record to a JSONL session log"
    )

    create = commands.add_parser(
        "create-character", help="guided character co-creation with the GM (D-005)"
    )
    create.add_argument("--campaign", metavar="SLUG")
    create.add_argument("--player", help="who is making this character")
    create.add_argument(
        "--show-prompt", action="store_true",
        help="print the co-creation system prompt and exit without calling a model",
    )
    create.add_argument(
        "--billing", choices=[b.value for b in Billing],
        help="override the sticky default for this session (D-004)",
    )
    create.add_argument(
        "--no-prompt", action="store_true", help="don't ask for billing; use the default"
    )
    create.add_argument(
        "--threshold", action="store_true", help="use the Opus escalation model (OD-3)"
    )
    create.add_argument("--max-tokens", type=int, default=1024)

    gm = commands.add_parser("gm", help="one GM narration turn")
    gm.add_argument("prompt")
    gm.add_argument("--campaign", metavar="SLUG", help="load a saved campaign's party and canon")
    gm.add_argument("--campaign-name", help="campaign title for the prompt header")
    gm.add_argument("--scene", help="where the party currently is")
    gm.add_argument("--canon", help="path to a canon ledger YAML file")
    gm.add_argument(
        "--character", action="append", metavar="PATH",
        help="a character sheet to put in the party (repeatable)",
    )
    gm.add_argument(
        "--resolution", action="append", metavar="TEXT",
        help="an engine result to hand the GM (repeatable) — e.g. "
             "'Stealth check: 17 vs DC 14, success'",
    )
    gm.add_argument(
        "--scaffolding", choices=sorted(SCAFFOLDING_TEMPLATES),
        help="override config's D-006 scaffolding level for this turn",
    )
    gm.add_argument(
        "--show-prompt", action="store_true",
        help="print the assembled prompt and exit without calling a model",
    )
    gm.add_argument(
        "--billing", choices=[b.value for b in Billing],
        help="override the sticky default for this session (D-004)",
    )
    gm.add_argument(
        "--no-prompt", action="store_true", help="don't ask for billing; use the default"
    )
    gm.add_argument(
        "--threshold", action="store_true",
        help="use the Opus escalation model (authored threshold moment, OD-3)",
    )
    gm.add_argument("--max-tokens", type=int, default=1024)
    gm.add_argument("--log", action="store_true", help="record to a JSONL session log")

    play = commands.add_parser("play", help="hot-seat play session (the turn loop)")
    play.add_argument(
        "--campaign", metavar="SLUG",
        help="play a saved campaign — its party and canon load from disk",
    )
    play.add_argument("--campaign-name", help="campaign title")
    play.add_argument("--scene", help="where the party starts")
    play.add_argument("--canon", help="path to a canon ledger YAML file")
    play.add_argument(
        "--character", action="append", metavar="PATH",
        help="a character sheet to put in the party (repeatable)",
    )
    play.add_argument(
        "--scaffolding", choices=sorted(SCAFFOLDING_TEMPLATES),
        help="override config's D-006 scaffolding level",
    )
    play.add_argument(
        "--billing", choices=[b.value for b in Billing],
        help="override the sticky default for this session (D-004)",
    )
    play.add_argument(
        "--no-prompt", action="store_true", help="don't ask for billing; use the default"
    )
    play.add_argument(
        "--threshold", action="store_true",
        help="use the Opus escalation model (authored threshold moment, OD-3)",
    )
    play.add_argument(
        "--seed", type=int, help="master seed (one is generated and logged if omitted)"
    )
    play.add_argument("--max-tokens", type=int, default=1024)

    sheet = commands.add_parser("sheet", help="character sheets")
    sheet_commands = sheet.add_subparsers(dest="sheet_command")
    sheet_show = sheet_commands.add_parser("show", help="render a sheet")
    sheet_show.add_argument("path")
    sheet_validate = sheet_commands.add_parser("validate", help="validate a sheet")
    sheet_validate.add_argument("path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    console = Console()

    # Before anything that might want a key. Resolved against the repo root, so `dndc`
    # works from any directory.
    load_env_file()

    if args.check_config:
        return _cmd_check_config(console)

    try:
        if args.command == "srd":
            if args.srd_command == "ingest":
                return _cmd_srd_ingest(console, args)
            if args.srd_command == "stats":
                return _cmd_srd_stats(console)
            if args.srd_command == "verify":
                return _cmd_srd_verify(console)
            parser.parse_args(["srd", "--help"])
            return 0

        if args.command == "new-campaign":
            return _cmd_new_campaign(console, args)
        if args.command == "campaigns":
            return _cmd_campaigns(console)
        if args.command == "roll":
            return _cmd_roll(console, args)
        if args.command == "create-character":
            return _cmd_create_character(console, args)
        if args.command == "gm":
            return _cmd_gm(console, args)
        if args.command == "play":
            return _cmd_play(console, args)
        if args.command == "sheet":
            if args.sheet_command == "show":
                return _cmd_sheet_show(console, args)
            if args.sheet_command == "validate":
                return _cmd_sheet_validate(console, args)
            parser.parse_args(["sheet", "--help"])
            return 0
    except SRDIngestError as exc:
        console.print(f"[red]error:[/red] {exc}")
        return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
