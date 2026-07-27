"""`dndc` entry point.

The `srd` command group lands with P0.2; the play-facing surface (new-campaign, roll,
sheet) is still P0.5's.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table

from dndc import __version__
from dndc.config import load_config
from dndc.schema.srd import IngestScope
from dndc.srd import SRDIngestError, ingest, load_dataset, validate_dataset, verify_pin


def _cmd_check_config(console: Console) -> int:
    cfg = load_config()
    console.print(f"[bold]billing default:[/bold] {cfg.billing.default.value}")
    console.print(f"[bold]gm:[/bold] {cfg.seats.gm.model_default} "
                  f"(threshold: {cfg.seats.gm.model_threshold})")
    console.print(f"[bold]npc:[/bold] {cfg.seats.npc.model} @ {cfg.seats.npc.endpoint}")
    console.print(f"[bold]utility:[/bold] {cfg.seats.utility.model} @ {cfg.seats.utility.endpoint}")
    return 0


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
        "--max-class-level",
        type=int,
        default=IngestScope().max_class_level,
        help="highest class level to ingest (default: %(default)s)",
    )
    srd_ingest.add_argument(
        "--max-cr",
        type=float,
        default=IngestScope().max_challenge_rating,
        help="highest monster challenge rating to ingest (default: %(default)s)",
    )
    srd_commands.add_parser("stats", help="summarize the normalized dataset")
    srd_commands.add_parser("verify", help="check the pin hashes and dataset integrity")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    console = Console()

    if args.check_config:
        return _cmd_check_config(console)

    if args.command == "srd":
        try:
            if args.srd_command == "ingest":
                return _cmd_srd_ingest(console, args)
            if args.srd_command == "stats":
                return _cmd_srd_stats(console)
            if args.srd_command == "verify":
                return _cmd_srd_verify(console)
        except SRDIngestError as exc:
            console.print(f"[red]error:[/red] {exc}")
            return 1
        parser.parse_args(["srd", "--help"])
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
