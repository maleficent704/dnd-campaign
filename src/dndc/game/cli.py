"""`dndc` entry point.

Skeleton only — the real command surface (new-campaign, roll, sheet) lands in P0.5.
"""

from __future__ import annotations

import argparse

from rich.console import Console

from dndc import __version__
from dndc.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dndc", description=__doc__)
    parser.add_argument("--version", action="version", version=f"dndc {__version__}")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate config.yaml and print the resolved model seats",
    )
    args = parser.parse_args(argv)

    console = Console()
    if args.check_config:
        cfg = load_config()
        console.print(f"[bold]billing default:[/bold] {cfg.billing.default.value}")
        console.print(f"[bold]gm:[/bold] {cfg.seats.gm.model_default} "
                      f"(threshold: {cfg.seats.gm.model_threshold})")
        console.print(f"[bold]npc:[/bold] {cfg.seats.npc.model} @ {cfg.seats.npc.endpoint}")
        console.print(f"[bold]utility:[/bold] {cfg.seats.utility.model} @ {cfg.seats.utility.endpoint}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
