"""`dndc` entry point.

Phase 0's command surface: `srd` (P0.2) and `new-campaign` / `roll` / `sheet` (P0.5).
The play loop itself arrives in Phase 1.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from dndc import __version__
from dndc.config import load_config
from dndc.game.campaign import CampaignError, campaign_dir, create_campaign, list_campaigns
from dndc.logging import SessionLog, git_commit_sha, resolve_log_dir
from dndc.rules.dice import Advantage, DiceError, roll, roll_d20
from dndc.schema.events import DiceRoll, RulesResolution, SeatInfo, SessionMeta
from dndc.schema.sheet import SKILL_ABILITY, Ability, CharacterSheet, Skill
from dndc.schema.srd import IngestScope
from dndc.srd import SRDIngestError, ingest, load_dataset, validate_dataset, verify_pin

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


def start_session_log(cfg, campaign: str | None = None, seed: int | None = None) -> SessionLog:
    """Open a session log and write its `session_meta` header (D-008)."""
    log = SessionLog.open(resolve_log_dir(cfg.logging.dir))
    sha, dirty = git_commit_sha() if cfg.logging.stamp_commit_sha else (None, False)
    log.emit(
        SessionMeta,
        dndc_version=__version__,
        commit_sha=sha,
        dirty_worktree=dirty,
        billing=cfg.billing.default.value,
        campaign=campaign,
        seats=_seats_for_meta(cfg),
        gameplay={
            "scaffolding": cfg.gameplay.scaffolding,
            "play_mode": cfg.gameplay.play_mode,
        },
        seed=seed,
    )
    return log


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
    console.print("  next: character co-creation lands in Phase 1 (P1.4)")
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
    return 0


def _cmd_sheet_validate(console: Console, args: argparse.Namespace) -> int:
    sheet = _load_sheet(console, args.path)
    if sheet is None:
        return 1
    console.print(f"[green]valid[/green] — {sheet.name}, level {sheet.level} "
                  f"{sheet.species} {sheet.character_class}")
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
