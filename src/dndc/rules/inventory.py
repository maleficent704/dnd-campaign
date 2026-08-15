"""Adding and removing items — the engine half of P2.4.

Pure functions over an inventory list: state in, new state out, no logging, no model, no
disk. The GM proposes an item change (`gm/inventorytag.py`), the table confirms it, and
this is the only code that performs one.

The interesting case is losing something the sheet does not have. That happens because
the fiction ran ahead of the state — the GM narrated a torch being handed over that was
never written down — and there are two bad answers to it. Refusing outright leaves the
sheet contradicting the story the table just played through. Pretending it worked hides a
divergence that Phase 7 is specifically built to see. So: **remove whatever is actually
there, and report that it did not match.** The caller records `applied: false` (D-008,
amended 2026-08-13), the CLI says so out loud, and nobody has to reconcile a sheet
against a transcript by hand later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from dndc.schema.events import InventoryDirection
from dndc.schema.sheet import InventoryItem

#: What an item is called and what it weighs, or `None` for something the ruleset has
#: never heard of. Passed in rather than looked up, so this module stays a pure function
#: over a list — the caller owns the SRD, as everything that touches it must.
Catalogue = Callable[[str], "tuple[str, float] | None"]


@dataclass(frozen=True)
class InventoryOutcome:
    """What one confirmed change did to an inventory."""

    inventory: tuple[InventoryItem, ...]
    #: The name the sheet ends up keyed on — the existing stack's spelling if there was
    #: one, so "Rope" and "rope" do not become two piles.
    item: str
    #: What was asked for, and what the sheet could honour. Equal in the ordinary case.
    quantity: int
    changed: int
    #: The sheet did exactly what was proposed. False is the fiction/state divergence.
    applied: bool
    #: Why not, in words the table can read. Empty when `applied`.
    note: str = ""


def apply_change(
    inventory: Sequence[InventoryItem],
    item: str,
    direction: InventoryDirection,
    quantity: int = 1,
    catalogue: Catalogue | None = None,
) -> InventoryOutcome:
    if direction is InventoryDirection.GAIN:
        return apply_gain(inventory, item, quantity, catalogue)
    return apply_lose(inventory, item, quantity)


def apply_gain(
    inventory: Sequence[InventoryItem],
    item: str,
    quantity: int = 1,
    catalogue: Catalogue | None = None,
) -> InventoryOutcome:
    """Add to an existing stack, or start one. A gain can always be honoured.

    `catalogue` is where the weight comes from. Without one a new item weighs nothing —
    which was the whole of P2.4's known gap, and made `carried_weight` a number that
    looked authoritative and was not. Still nothing when the ruleset has no entry: the GM
    may hand someone a keepsake, and a fabricated weight would be worse than an absent
    one (Fable scheduled this with the ingest, 2026-08-14).
    """
    quantity = max(int(quantity), 1)
    name = item.strip()
    items = list(inventory)

    index = _find(items, name)
    if index is None:
        known = catalogue(name) if catalogue is not None else None
        if known is not None:
            # The ruleset's spelling wins, so "a rope" and "Rope, hempen (50 feet)" do
            # not become two piles the moment one of them is picked up again.
            name, weight = known
            index = _find(items, name)
            if index is not None:
                held = items[index]
                items[index] = held.model_copy(update={"quantity": held.quantity + quantity})
                return InventoryOutcome(
                    inventory=tuple(items), item=held.name, quantity=quantity,
                    changed=quantity, applied=True,
                )
        else:
            weight = 0.0
        items.append(InventoryItem(name=name, quantity=quantity, weight=weight))
        return InventoryOutcome(
            inventory=tuple(items), item=name, quantity=quantity, changed=quantity, applied=True
        )

    held = items[index]
    items[index] = held.model_copy(update={"quantity": held.quantity + quantity})
    return InventoryOutcome(
        inventory=tuple(items),
        item=held.name,
        quantity=quantity,
        changed=quantity,
        applied=True,
    )


def apply_lose(
    inventory: Sequence[InventoryItem], item: str, quantity: int = 1
) -> InventoryOutcome:
    """Take from a stack, emptying it if need be. See the module docstring for why a
    loss the sheet cannot cover still happens, and is still flagged."""
    quantity = max(int(quantity), 1)
    name = item.strip()
    items = list(inventory)

    index = _find(items, name)
    if index is None:
        return InventoryOutcome(
            inventory=tuple(items),
            item=name,
            quantity=quantity,
            changed=0,
            applied=False,
            note="not on the sheet",
        )

    held = items[index]
    if held.quantity <= quantity:
        del items[index]
        short = held.quantity < quantity
        return InventoryOutcome(
            inventory=tuple(items),
            item=held.name,
            quantity=quantity,
            changed=held.quantity,
            applied=not short,
            note=f"only {held.quantity} on the sheet" if short else "",
        )

    items[index] = held.model_copy(update={"quantity": held.quantity - quantity})
    return InventoryOutcome(
        inventory=tuple(items),
        item=held.name,
        quantity=quantity,
        changed=quantity,
        applied=True,
    )


def _find(items: Sequence[InventoryItem], name: str) -> int | None:
    """Match a stack by name, ignoring case, spacing and trailing punctuation.

    The GM writes "the rope" this turn and "Rope" the next (the tag parser has already
    taken the article off), and a sheet that grows a second pile each time is worse than
    no tracking at all. Singular/plural are deliberately *not* equated: a matcher loose
    enough to merge "torch" with "torches" is loose enough to merge "potion of healing"
    with "potions of healing greater", and a wrong merge silently destroys an item.
    """
    wanted = _key(name)
    for index, held in enumerate(items):
        if _key(held.name) == wanted:
            return index
    return None


def _key(name: str) -> str:
    return " ".join(name.casefold().split()).rstrip(".,;:")
