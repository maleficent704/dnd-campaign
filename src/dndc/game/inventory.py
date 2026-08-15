"""Performing the item changes the GM proposed (P2.4).

`rules/inventory.py` is the pure half — a list of items in, a new list out. This is the
thing that owns the sheets during a session: it resolves which character a tag meant,
performs the change, writes the sheet back to disk, and logs the `inventory_change` event.

Three states a proposal can end in, and all three are logged:

* **confirmed and applied** — the table said yes and the sheet could do it;
* **confirmed, not applied** — the table said yes and the sheet could not (the GM narrated
  losing something that was never written down). `applied: false` is the divergence
  Finding 5 recorded, now visible as a field instead of as a discrepancy nobody noticed;
* **declined** — the table said no. Logged with `confirmed: false`, sheet untouched. What
  the GM thought had happened and the players did not is a measurement of the GM.

**Saved on every change**, for the same reason the canon ledger is: a session that dies at
turn 40 must not take the party's gear with it. The write is atomic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

from dndc.game.party import resolve_member
from dndc.gm.inventorytag import InventoryTag
from dndc.logging import SessionLog
from dndc.rules.inventory import InventoryOutcome, apply_change
from dndc.schema.events import InventoryChange, InventoryDirection
from dndc.schema.sheet import CharacterSheet
from dndc.srd.repository import SRDRepository


class InventoryStore:
    """The party's sheets, their files, and the log."""

    def __init__(
        self, log: SessionLog | None = None, repo: SRDRepository | None = None
    ) -> None:
        self.log = log
        #: Where a gained item's weight and canonical spelling come from. Optional
        #: because the store is used in tests and scratch sessions with no dataset; the
        #: cost of going without is a weightless item, which is what P2.4 shipped with.
        self.repo = repo
        self._sheets: dict[str, CharacterSheet] = {}
        self._paths: dict[str, Path] = {}

    def catalogue(self, name: str) -> tuple[str, float] | None:
        """The ruleset's answer for an item, or None for something it never heard of."""
        if self.repo is None:
            return None
        item = self.repo.equipment(name)
        return (item.name, item.weight) if item is not None else None

    @classmethod
    def for_sheets(
        cls,
        sheets: Iterable[CharacterSheet],
        directory: Path | str | None = None,
        log: SessionLog | None = None,
    ) -> InventoryStore:
        """`directory` is a campaign's `characters/`. None means in-memory: a scratch
        session still logs its item changes, it just has nowhere durable to file them."""
        store = cls(log=log)
        for sheet in sheets:
            store.add(sheet, directory=directory)
        return store

    def add(
        self,
        sheet: CharacterSheet,
        path: Path | str | None = None,
        directory: Path | str | None = None,
    ) -> None:
        from dndc.schema.campaign import slugify

        self._sheets[_key(sheet.name)] = sheet
        if path is not None:
            self._paths[_key(sheet.name)] = Path(path)
        elif directory is not None:
            self._paths[_key(sheet.name)] = Path(directory) / f"{slugify(sheet.name)}.yaml"

    # --- resolution ---------------------------------------------------------

    def resolve(self, name: str | None, default: str | None = None) -> CharacterSheet | None:
        """Which sheet a tag meant. `None` when the GM named nobody the party has.

        A tag with no name means the character whose turn it is — that is the ordinary
        case and the reason the name is optional in the wire format. A tag naming someone
        unknown resolves to nothing rather than to the default: the GM handing a lantern
        to a character who does not exist is a thing worth seeing in the log, not a thing
        to quietly give to whoever happens to be acting.
        """
        if name is None or not name.strip():
            return self._sheets.get(_key(default)) if default else None

        # The same tiered matcher `/switch` uses: "Corin" for "Corin Vale", "Hammond" for
        # "Brother Hammond". Ambiguity resolves to nobody — with two Corins at the table,
        # guessing which one gets the sword is not the engine's call, and the proposal is
        # logged either way so refusing costs nothing.
        matches = resolve_member(name, list(self._sheets.values()))
        return matches[0] if len(matches) == 1 else None

    # --- writes -------------------------------------------------------------

    def apply(
        self,
        tag: InventoryTag,
        sheet: CharacterSheet,
        turn: int | None = None,
    ) -> InventoryOutcome:
        """Perform a confirmed change, save the sheet, log what happened."""
        outcome = apply_change(
            sheet.inventory, tag.item, tag.direction, tag.quantity, self.catalogue
        )
        # Assigned rather than rebuilt: the CLI, the turn engine and this store all hold
        # the same sheet object, and a copy here would leave two of them looking at the
        # inventory the party had a moment ago.
        sheet.inventory = list(outcome.inventory)
        self.save(sheet)
        self._emit(tag, sheet.name, confirmed=True, applied=outcome.applied, turn=turn)
        return outcome

    def decline(
        self,
        tag: InventoryTag,
        character: str,
        turn: int | None = None,
    ) -> InventoryChange | None:
        """The table said no, or there was nobody to give it to. Nothing is touched."""
        return self._emit(tag, character, confirmed=False, applied=False, turn=turn)

    # --- persistence --------------------------------------------------------

    def path_for(self, sheet: CharacterSheet) -> Path | None:
        return self._paths.get(_key(sheet.name))

    def save(self, sheet: CharacterSheet) -> Path | None:
        """Atomically rewrite one sheet. No path configured is not an error."""
        path = self.path_for(sheet)
        if path is None:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(sheet.to_yaml(), encoding="utf-8")
        os.replace(temp, path)
        return path

    # --- logging ------------------------------------------------------------

    def _emit(
        self,
        tag: InventoryTag,
        character: str,
        confirmed: bool,
        applied: bool,
        turn: int | None = None,
    ) -> InventoryChange | None:
        if self.log is None:
            return None
        return self.log.emit(
            InventoryChange,
            character=character,
            item=tag.item,
            quantity=tag.quantity,
            direction=tag.direction,
            established_by=tag.raw or None,
            confirmed=confirmed,
            applied=applied,
            # The turn ordinal within the session, matching `CanonEntry.turn` — the log's
            # own `seq` already orders these, so what analysis needs from this field is
            # which exchange it belongs to.
            turn_seq=turn,
        )


def _key(name: str | None) -> str:
    return " ".join((name or "").casefold().split())


def describe_change(
    outcome: InventoryOutcome, direction: InventoryDirection, character: str
) -> str:
    """One line for the table, saying what the sheet now holds."""
    verb = "gains" if direction is InventoryDirection.GAIN else "loses"
    count = f" ×{outcome.quantity}" if outcome.quantity > 1 else ""
    line = f"{character} {verb} {outcome.item}{count}"
    if not outcome.applied:
        line += f" — {outcome.note or 'sheet unchanged'}"
    return line


def proposals_for(
    tags: Sequence[InventoryTag], store: InventoryStore, acting: str | None
) -> list[tuple[InventoryTag, CharacterSheet | None]]:
    """Pair each tag with the sheet it meant, or None if there is no such character."""
    return [(tag, store.resolve(tag.character, default=acting)) for tag in tags]
