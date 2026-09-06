"""Building an evening, with nobody necessarily standing at a terminal (P6.7b-ii).

`_cmd_play` used to do this itself: about a hundred and twenty lines that load a
campaign, settle billing, open a log, run the recap, warm the NPC seat, read the SRD,
build the engine and start the session — every one of them reachable only through a
`rich.Console`. That was fine while the only way to start an evening was to type
`dndc play`. It stops being fine the moment a browser wants to start one, because a
browser has no console to pass and there is nobody sitting at the process's stdin.

So this module owns construction and the CLI owns the terminal. The seam is `Herald`:
a small thing that can be told something, shown that work is happening, and asked a
question — the three things setup actually did with a console. `ConsoleHerald` in the
CLI is a thin wrapper around `console.print` and `Prompt.ask`, which is why this
extraction changes no terminal output; `QuietHerald` here is what a caller with nobody
to talk to uses, and it keeps what it was told so the lines are not simply lost.

**This is a refactor and it is meant to be a boring one.** Nothing observable moves.
The one contract that did change is failure: `load_sheet` and `load_party` used to
print a red line and return `None`, which meant every caller had to remember to check
and no caller that was not a terminal could use them at all. They raise `SetupError`
now, which carries both the sentence and the markup the terminal used to print, so the
CLI's output is unchanged and a browser gets the same failures in words it can render.

What is deliberately *not* done here: `build_evening` still takes an `argparse.Namespace`.
Inventing a request object before P6.7b-iii knows what a browser will actually send would
be designing against a guess. The parameter is `args` and it is honest about that.
"""

from __future__ import annotations

import argparse
import random
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ContextManager, Protocol, Sequence

from pydantic import ValidationError

from dndc import __version__
from dndc.config import Billing, save_billing_default
from dndc.game.beliefturn import StanceKeeper
from dndc.game.campaign import (
    CHARACTERS_DIRNAME,
    CampaignError,
    campaign_dir,
    load_campaign,
)
from dndc.game.creation import (
    load_campaign_canon,
    load_campaign_chronicle,
    load_campaign_npcs,
    load_campaign_sheets,
)
from dndc.game.inventory import InventoryStore
from dndc.game.npcturn import NPCVoice
from dndc.game.saves import Resume, SaveError, SaveStore
from dndc.game.session import (
    PlaySession,
    SessionError,
    acting_member,
    build_engine,
    resume_from,
)
from dndc.gm import CampaignContext, CanonLedger, PartyMember
from dndc.gm.gatekeeper import Gatekeeper
from dndc.gm.stance import StanceJudge
from dndc.logging import SessionLog, git_commit_sha, resolve_log_dir
from dndc.memory import RECAP_TEMPERATURE, CanonStore, Recapper
from dndc.models import (
    BATCH_SEAT,
    INTERACTIVE_SEAT,
    THROTTLE_WARNING,
    GMBackendError,
    OllamaRouter,
    RoutingError,
    build_batch_backend,
    build_gm_backend,
    build_interactive_backend,
    build_npc_backend,
    load_prices,
)
from dndc.schema.campaign import slugify
from dndc.schema.events import SeatInfo, SessionMeta
from dndc.schema.sheet import CharacterSheet
from dndc.srd import SRDIngestError
from dndc.srd.repository import SRDRepository

MAX_SEED = 2**32

#: Judgement wants no creativity: the same draft should get the same verdict twice.
GATEKEEPER_TEMPERATURE = 0.0


class SetupError(RuntimeError):
    """An evening that could not be built, and the sentence to show for it.

    `str(exc)` is the plain sentence — for a log, a browser, or anything that has no
    colours. `markup` is what the terminal prints, and it defaults to the `[red]error:`
    shape the CLI used for almost all of these. They travel together because the CLI
    used to hold both, and a caller forced to reinvent the wording is a caller that
    will word it differently.
    """

    def __init__(self, message: str, markup: str | None = None) -> None:
        super().__init__(message)
        self.markup = markup or f"[red]error:[/red] {message}"


class Herald(Protocol):
    """Whoever is being told how the evening is coming together.

    Three verbs, because three are what setup ever did with a console: say a line,
    show that something slow is happening, and put a question. `can_ask` is the fourth
    thing it did — `sys.stdin.isatty()` — asked once here instead of in the middle of
    `resolve_billing`, because whether there is anybody to ask is a property of who is
    listening and not of the billing decision.

    `ask` returns `None` for every way of not getting an answer: no terminal, EOF, a
    Ctrl-C mid-question, a browser that closed. Callers treat them alike, which they
    already did — the CLI's `except (EOFError, KeyboardInterrupt): return False` was
    the same rule written twice.
    """

    @property
    def can_ask(self) -> bool:
        """Whether there is anybody on the other end to put a question to."""

    def say(self, text: str) -> None:
        """One line. Rich markup, because the terminal is still the main audience."""

    def working(self, text: str) -> ContextManager[Any]:
        """Wrap something slow enough that silence would look like a hang."""

    def ask(
        self, prompt: str, default: str = "", choices: Sequence[str] | None = None
    ) -> str | None:
        """Put a question. `None` means no answer came, for any reason."""


@dataclass
class QuietHerald:
    """A herald with nobody to talk to — the headless default.

    It keeps what it was told rather than dropping it. Nothing reads `said` yet; the
    point is that the recap's "Previously on…" and the NPC seat's warnings are the
    lines a browser will most want when P6.7b-iii gives it somewhere to put them, and
    a construction path that has already thrown them away cannot be asked for them
    later.
    """

    said: list[str] = field(default_factory=list)

    @property
    def can_ask(self) -> bool:
        return False

    def say(self, text: str) -> None:
        self.said.append(text)

    def working(self, text: str) -> ContextManager[Any]:
        self.said.append(text)
        return nullcontext()

    def ask(
        self, prompt: str, default: str = "", choices: Sequence[str] | None = None
    ) -> str | None:
        return None


def load_sheet(path: str) -> CharacterSheet:
    """A character sheet off disk, or a `SetupError` saying why not.

    It used to print and return `None`, which meant every caller had to remember to
    check, and no caller that was not a terminal could use it at all. Raising costs the
    three CLI callers one `except` each and buys a browser the same three failures with
    the same three sentences.
    """
    target = Path(path)
    if not target.exists():
        raise SetupError(
            f"no sheet at {target}", markup=f"[red]error:[/red] no sheet at {target}"
        )
    try:
        return CharacterSheet.load(target)
    except ValidationError as exc:
        problems = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "(root)"
            problems.append(f"{location}: {error['msg']}")
        lines = [f"[red]invalid sheet[/red] {target}:"]
        lines += [f"  - {problem}" for problem in problems]
        raise SetupError(
            f"invalid sheet {target}: " + "; ".join(problems),
            markup="\n".join(lines),
        ) from exc
    except Exception as exc:  # malformed YAML
        raise SetupError(
            f"could not read {target}: {exc}",
            markup=f"[red]could not read[/red] {target}: {exc}",
        ) from exc


@dataclass
class LoadedParty:
    """What a session needs about its characters: the prompt's view, the engine's, and
    the files they came from — kept apart because they are three different things."""

    campaign: CampaignContext
    sheets: dict[str, CharacterSheet]
    #: Where each sheet lives, so P2.4 can write an item change back to it. A sheet with
    #: no path is in-memory only.
    paths: dict[str, Path]


def load_party(args: argparse.Namespace) -> LoadedParty:
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
    paths: dict[str, Path] = {}

    if slug:
        try:
            record = load_campaign(slug)
        except (CampaignError, ValidationError) as exc:
            raise SetupError(str(exc)) from exc
        campaign.name = args.campaign_name or record.name
        campaign.ledger = load_campaign_canon(slug)
        campaign.chronicle = load_campaign_chronicle(slug)
        characters = campaign_dir(slug) / CHARACTERS_DIRNAME
        for sheet in load_campaign_sheets(slug):
            campaign.party.append(PartyMember.from_sheet(sheet))
            sheets[sheet.name.lower()] = sheet
            paths[sheet.name.lower()] = characters / f"{slugify(sheet.name)}.yaml"

    campaign.scene = args.scene or ""
    if args.canon:
        campaign.ledger = CanonLedger.load(args.canon)

    for path in args.character or ():
        sheet = load_sheet(path)
        if sheet.name.lower() in sheets:
            continue
        campaign.party.append(PartyMember.from_sheet(sheet))
        sheets[sheet.name.lower()] = sheet
        # A sheet passed by path is written back to that path. Unlike `--canon`, which
        # loads a ledger for inspection, `--character` *is* where that character lives.
        paths[sheet.name.lower()] = Path(path)
    return LoadedParty(campaign=campaign, sheets=sheets, paths=paths)


def _announce_resume(herald: Herald, resume: Resume) -> None:
    """Say what was picked up, in the terms the table would use."""
    when = resume.save.saved_at.strftime("%Y-%m-%d %H:%M")
    if resume.continuing:
        herald.say(
            f"[green]resuming[/green] session {resume.session_id} — "
            f"{resume.turns} turns, saved {when} UTC"
        )
        return
    if not resume.save.closed:
        # An open save whose log has been cleaned away: the scene and the window are
        # still good, but this run cannot honestly claim to continue that session's
        # record, so it starts its own and says where it came from.
        herald.say(
            f"[yellow]resuming[/yellow] {resume.turns} turns — the previous log is gone, "
            f"so this is a new session record"
        )
        return
    herald.say(
        f"[green]picking up[/green] where the last session left off "
        f"({resume.played} turns, ended {when} UTC) — the scene is remembered; what "
        f"happened is the chronicle's now"
    )


def _seats_for_meta(cfg) -> dict[str, SeatInfo]:
    """Snapshot the resolved seats so a log says what actually ran."""
    return {
        "gm": SeatInfo(backend=cfg.seats.gm.backend, model=cfg.seats.gm.model_default),
        "npc": SeatInfo(
            backend=cfg.seats.npc.backend,
            model=cfg.seats.npc.model,
            endpoint=cfg.seats.npc.endpoint,
        ),
        # Both utility seats, keyed by the same names the `cost` rows use — a log that
        # cannot say which of them ran cannot answer the question the split was made to
        # answer (Fable, 2026-08-14).
        INTERACTIVE_SEAT: SeatInfo(
            backend=cfg.seats.utility_interactive.backend,
            model=cfg.seats.utility_interactive.model,
            endpoint=cfg.seats.utility_interactive.endpoint,
        ),
        BATCH_SEAT: SeatInfo(
            backend=cfg.seats.utility_batch.backend,
            model=cfg.seats.utility_batch.model,
            endpoint=cfg.seats.utility_batch.endpoint,
        ),
    }


def start_session_log(
    cfg,
    campaign: str | None = None,
    seed: int | None = None,
    billing: Billing | None = None,
    resume: Resume | None = None,
) -> SessionLog:
    """Open a session log and write its `session_meta` header (D-008).

    A `resume` that is *continuing* reopens the save point's own log rather than starting
    a new one, and `SessionLog.open` picks `seq` up from the highest already on disk — the
    npc-village rider, doing the job it was ported for. The second `session_meta` row in
    that file is not a duplicate: the process restarted, and the commit, the seat and the
    seed it restarted on are all free to have changed (D-008 item 27).
    """
    if resume is not None and resume.continuing and resume.log_path is not None:
        log = SessionLog.open(resume.log_path.parent, session_id=resume.log_path.stem)
    else:
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
        resumed_from=resume.session_id if resume is not None else None,
        resumed_turns=resume.played if resume is not None else 0,
    )
    return log


def resolve_billing(
    cfg,
    herald: Herald,
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
    elif ask and herald.can_ask:
        default = cfg.billing.default
        herald.say(
            f"[bold]billing[/bold] — [cyan]api[/cyan] (metered, spend-capped) or "
            f"[cyan]subscription[/cyan] (weekly Max pool)"
        )
        answer = herald.ask("  mode", default=default.value, choices=[b.value for b in Billing])
        # `can_ask` said somebody was there, so `None` here means they left mid-question
        # (^D, ^C) rather than that nobody was listening. The sticky default is the same
        # answer either way, and it is the one this session would have used anyway.
        choice = Billing(answer) if answer else default
    else:
        choice = cfg.billing.default

    if choice is Billing.SUBSCRIPTION:
        herald.say(f"[yellow]heads-up:[/yellow] {THROTTLE_WARNING}")

    if remember and choice is not cfg.billing.default and save_billing_default(choice):
        herald.say(f"[dim]sticky default is now {choice.value}[/dim]")
    return choice


def _build_gate(cfg, args, herald) -> tuple[Gatekeeper | None, object | None]:
    """The output gate and the backend to close afterwards, or (None, None) if ungated.

    Which seat checks is a flag rather than a constant because the two candidates trade
    against each other and the trade is measurable: `utility_interactive` is the seat
    defined as "the jobs the table waits on", and `utility_batch` is the better reader. Run
    `dndc npc control` against both before believing either.
    """
    if getattr(args, "ungated", False):
        return None, None
    backend = _utility_backend(cfg, args)
    _warn_if_thrashing(cfg, backend, herald)
    return Gatekeeper(backend=backend), backend


def _utility_backend(cfg, args):
    """The utility seat the tier's second calls run on — the gate, and the P4.6 judge.

    One function because they must land on the same seat: two different models on one host
    evict each other, and the whole point of `_warn_if_thrashing` is that the tier's extra
    calls are cheap only while everything stays resident.
    """
    build = build_batch_backend if args.gate_seat == BATCH_SEAT else build_interactive_backend
    return build(cfg, temperature=GATEKEEPER_TEMPERATURE)


def _warn_if_thrashing(cfg, gate_backend, herald: Herald) -> None:
    """A gate on a *different* model at the *same* endpoint reloads both, every line.

    Measured on toto-llm 2026-09-02 (e): llama3.3:70b and llama3.1:8b do not coexist
    there — each evicts the other — so alternating an NPC call and a gate check across
    them costs a ~70 s reload **per line**, not the ~1.5 s the gate itself takes. This is
    a property of that box's VRAM rather than of the design, which is exactly why it is a
    warning and not a refusal: a machine that fits both should not be told it cannot.
    """
    npc_seat = cfg.seats.npc
    if gate_backend.endpoint.rstrip("/") != npc_seat.endpoint.rstrip("/"):
        return
    if gate_backend.model == npc_seat.model:
        return
    herald.say(
        f"[yellow]warning:[/yellow] the gate runs {gate_backend.model} where the NPC seat "
        f"runs {npc_seat.model}, on the same host. If that host cannot hold both, every "
        f"line will reload a model (~70 s on toto-llm). Prefer a gate seat whose model "
        f"matches the NPC seat's."
    )


def _build_voice(herald: Herald, cfg, args, log) -> tuple[object | None, object, list]:
    """The NPC tier for a play session: the voice, the supersession keeper, and closers.

    **Fails open the whole way down.** No cast, a routing failure, a host that has gone
    away — every one of them returns None and the session plays on with the GM voicing
    everyone in its own prose, which is what it did for three phases. A local box being
    off is not a reason a table cannot play, and the alternative (refusing to start) would
    make the NPC tier a single point of failure for the entire game.
    """
    if getattr(args, "no_npcs", False) or not getattr(args, "campaign", None):
        return None, StanceKeeper(log=log), []
    book = load_campaign_npcs(args.campaign)
    if not len(book):
        return None, StanceKeeper(log=log), []

    try:
        backend, route = build_npc_backend(cfg, OllamaRouter.for_config(cfg))
    except RoutingError as exc:
        herald.say(f"[yellow]NPC seat unavailable:[/yellow] {exc}")
        herald.say("[dim]the GM will voice everyone in its own prose[/dim]")
        return None, StanceKeeper(log=log), []

    closers = [backend]
    gate, gate_backend = _build_gate(cfg, args, herald)
    if gate_backend is not None:
        closers.append(gate_backend)
    voice = NPCVoice(backend=backend, log=log, route=route, gate=gate)

    # The supersession judge shares the gate's seat when there is one. `--ungated` turns
    # off the *output* gate — what the table sees — and says nothing about whether a
    # character may hold two contradictory beliefs at once, so the judge is built either
    # way. It is the same seat and the same temperature; sharing the backend keeps the
    # host holding one model.
    judge_backend = gate_backend
    if judge_backend is None:
        judge_backend = _utility_backend(cfg, args)
        closers.append(judge_backend)
    stance = StanceKeeper(judge=StanceJudge(backend=judge_backend), log=log)

    where = route.endpoint.name if route else backend.endpoint
    gated = "gated" if gate is not None else "[yellow]ungated[/yellow]"
    herald.say(
        f"[dim]{len(book)} NPC(s) speaking for themselves · {backend.model} on {where} ·[/dim] "
        f"{gated}"
    )
    if route is not None and route.fell_back:
        herald.say(f"[yellow]fell back[/yellow] [dim]— {route.reason}[/dim]")

    # The warm-up (P4.5). A 70B that is not resident costs ~68 s on its first call, and
    # unpaid that lands on whichever player speaks to somebody first. Paying it here moves
    # it to the one moment nobody is waiting, and printing the elapsed time makes the
    # difference between "already loaded" and "just loaded 40 GB" a measurement rather
    # than an inference — the 2026-09-02 (e) lesson, wired in.
    try:
        with herald.working("[dim]warming the NPC seat…[/dim]"):
            elapsed = voice.warm_up()
    except Exception as exc:
        herald.say(f"[yellow]warm-up failed:[/yellow] {type(exc).__name__}: {exc}")
        herald.say("[dim]NPCs stay on; the first line will pay the load instead[/dim]")
        return voice, stance, closers
    herald.say(f"[dim]seat warm in {elapsed} ms{_warmth(elapsed)}[/dim]")
    return voice, stance, closers


#: Above this, the warm-up call clearly loaded the model rather than merely answering.
#: Not a threshold anything branches on — it decides one word of console text.
COLD_LOAD_MS = 10_000


def _warmth(elapsed_ms: int) -> str:
    return " (it was cold)" if elapsed_ms >= COLD_LOAD_MS else " (already resident)"


def _pronouns(campaign) -> dict[str, str]:
    """How to refer to everyone this campaign has recorded pronouns for.

    Party and cast together, because the layers that read this write about both. Only
    names with an actual entry appear — a blank stays blank all the way down, and the
    prompts say to write around a name rather than choose for it. The cast is filtered
    again downstream against what the session named; handing over a roster and handing
    over a vocabulary are not the same thing (P4.1).
    """
    people = [(member.name, member.pronouns) for member in campaign.party]
    people += [(npc.name, npc.pronouns) for npc in campaign.cast]
    return {name: pronouns for name, pronouns in people if pronouns}


def _player_known(ledger) -> list[str]:
    """What the players already know, and only that.

    One rule, one place: `for_players` is the ledger's own allow-list (P6.2), and the
    recap and a browser must not be able to disagree about what the table knows. This
    used to be a second copy of the same scope test, which is precisely the shape of
    thing that drifts.
    """
    return [entry.text for entry in ledger.for_players()]


def _run_recap(
    herald: Herald, cfg, campaign, args: argparse.Namespace, log: SessionLog
) -> None:
    """"Previously on..." before the first turn (P5.3).

    Best-effort like the sweep and the chronicle: an evening must not fail to start
    because the GPU box is asleep. It runs before the NPC tier is built, which means the
    cold load of the 70B is paid by a call the table wanted anyway rather than by the
    throwaway warm-up — same model, same host.
    """
    if not len(campaign.chronicle):
        return

    backend = build_batch_backend(cfg, temperature=RECAP_TEMPERATURE)
    recapper = Recapper(
        backend=backend,
        log=log,
        party=[member.name for member in campaign.party],
        pronouns=_pronouns(campaign),
    )
    herald.say(
        f"\n[dim]previously — {cfg.seats.utility_batch.model} reading the campaign "
        f"back (a minute or two)...[/dim]"
    )
    try:
        report = recapper.recap(
            campaign.name, campaign.chronicle, known=_player_known(campaign.ledger)
        )
    finally:
        backend.close()

    if not report.shown:
        if report.invented:
            herald.say(
                f"[yellow]no recap[/yellow] — it invented {', '.join(report.invented)}"
            )
        elif report.error:
            herald.say(f"[yellow]no recap[/yellow] — {report.error}")
        recapper.record(report)
        return

    herald.say(f"\n[bold]Previously on {campaign.name}[/bold]")
    herald.say(f"  {report.text}\n")

    if report.scene and report.scene.strip() != campaign.scene.strip():
        report.scene_accepted = _confirm_scene(herald, campaign, report.scene)
    recapper.record(report)


def _confirm_scene(herald: Herald, campaign, proposed: str) -> bool:
    """Offer the recap's guess at where the party is standing. Silence keeps the old one.

    Confirmed rather than applied, because it is a guess about the one field that decides
    where the evening opens, and the two people who were actually there are sitting right
    here. An interrupted or piped session keeps whatever was saved, which is what it did
    before this existed.
    """
    if campaign.scene:
        herald.say(f"[dim]the scene on file: {campaign.scene}[/dim]")
    herald.say(f"[dim]where the recap thinks you are: {proposed}[/dim]")
    answer = herald.ask(
        "  [cyan]open here?[/cyan] enter to accept, [dim]n[/dim] to keep the old "
        "scene, or type a new one",
        default="",
    )
    if answer is None:
        return False

    answer = answer.strip()
    if answer.casefold() in {"n", "no"}:
        return False
    campaign.scene = proposed if not answer else answer
    return not answer


def _canon_store(args: argparse.Namespace, campaign, log: SessionLog) -> CanonStore:
    """Where this session's canon gets filed.

    A campaign has a `canon.yaml` and the world survives the process. A scratch session
    (`--character` with no campaign, or an explicit `--canon` file) gets an in-memory
    store: it still logs `canon_write` events, it just has nowhere durable to put them.
    Writing into a `--canon` file passed for inspection would be a surprise — that flag
    loads a ledger, it does not adopt one.
    """
    slug = getattr(args, "campaign", None)
    if not slug or args.canon:
        return CanonStore(campaign.ledger, log=log)
    return CanonStore.for_campaign(campaign_dir(slug), log=log)


@dataclass
class Evening:
    """An evening built and not yet opened.

    Everything a front end needs to run the loop, and nothing about *how* it runs one:
    there is no console here, no floor and no mirror, because those are choices about
    who is playing rather than about what was built. `session.open_scene` is still the
    caller's to make — construction stopping one step short of the first narration is
    what lets a browser decide when the evening actually starts.
    """

    campaign: CampaignContext
    session: PlaySession
    engine: Any
    items: InventoryStore
    log: SessionLog
    backend: Any
    billing: Billing
    seed: int
    saves: SaveStore | None
    resume: Resume | None


def build_evening(cfg, args: argparse.Namespace, herald: Herald) -> Evening:
    """Everything between "play this campaign" and a session waiting for its first line.

    Ordering here is load-bearing and was worked out over Phases 1–5; it is preserved
    exactly rather than tidied. In particular the recap runs *before* the NPC tier is
    built, so the 70B's cold load is paid by a call the table wanted anyway; and the
    seed is drawn before the log is opened, so `session_meta` can record it.

    Raises `SetupError` for every way this can fail. It used to be five different
    prints and five `return 1`s.
    """
    loaded = load_party(args)
    campaign, loaded_sheets = loaded.campaign, loaded.sheets
    if not campaign.party:
        raise SetupError(
            "no characters loaded — pass --campaign SLUG (after `dndc create-character`) "
            "or --character PATH.",
            markup=(
                "[yellow]no characters loaded[/yellow] — pass --campaign SLUG (after "
                "`dndc create-character`) or --character PATH."
            ),
        )

    saves = SaveStore.for_campaign(args.campaign) if args.campaign else None
    resume: Resume | None = None
    if saves is not None and not args.fresh:
        try:
            resume = resume_from(saves, campaign, scene=args.scene or "")
        except SaveError as exc:
            raise SetupError(str(exc)) from exc
        if resume is not None:
            _announce_resume(herald, resume)

    billing = resolve_billing(cfg, herald, requested=args.billing, ask=not args.no_prompt)
    try:
        backend = build_gm_backend(cfg, billing, threshold=args.threshold)
    except GMBackendError as exc:
        raise SetupError(str(exc)) from exc

    seed = args.seed if args.seed is not None else random.randrange(MAX_SEED)
    log = start_session_log(
        cfg, campaign=campaign.name, seed=seed, billing=billing, resume=resume
    )
    if not args.no_recap:
        _run_recap(herald, cfg, campaign, args, log)
    voice, stance, voice_closers = _build_voice(herald, cfg, args, log)
    # The roster and the tier are the same switch: the GM is shown who speaks for
    # themselves only when somebody actually can. A roster with no seat behind it would
    # have the GM directing characters into silence all session.
    if voice is not None:
        campaign.cast = list(load_campaign_npcs(args.campaign))

    # The dataset is what gives a picked-up item its weight (P2.4's known gap, closed
    # with the ingest task). A session without an ingested SRD still plays; items just
    # weigh nothing, which is what they did before.
    try:
        repo = SRDRepository.load()
    except SRDIngestError:
        repo = None
    items = InventoryStore(log=log, repo=repo)
    for key, sheet in loaded_sheets.items():
        items.add(sheet, path=loaded.paths.get(key))

    engine = build_engine(
        campaign,
        backend,
        log=log,
        scaffolding=args.scaffolding or cfg.gameplay.scaffolding,
        seed=seed,
        max_tokens=args.max_tokens,
        billing=billing.value,
        prices=load_prices(cfg.pricing),
        canon=_canon_store(args, campaign, log),
        voice=voice,
        stance=stance,
    )
    try:
        session = PlaySession.start(
            campaign,
            loaded_sheets,
            backend=backend,
            log=log,
            engine=engine,
            items=items,
            acting=acting_member(campaign, resume),
            billing=billing.value,
            seed=seed,
            saves=saves,
            resume=resume,
            closers=voice_closers,
        )
    except SessionError as exc:
        raise SetupError(str(exc)) from exc

    return Evening(
        campaign=campaign,
        session=session,
        engine=engine,
        items=items,
        log=log,
        backend=backend,
        billing=billing,
        seed=seed,
        saves=saves,
        resume=resume,
    )
