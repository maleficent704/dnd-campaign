"""Parsing the GM's `[[GAIN: ...]]` / `[[LOSE: ...]]` tags (P2.4) — items are state.

The first playtest ended with the party carrying, in the fiction, several things no sheet
had ever heard of. Fable ruled on that (2026-08-05): items are state, so the GM may
*propose* a change but never perform one — the same split `[[CHECK]]` draws around dice.
D-008 (amended 2026-08-13) specifies the wire format:

    [[GAIN: <character> — <item> ×<quantity>]]
    [[LOSE: <character> — <item> ×<quantity>]]

Character and quantity are optional. `[[GAIN: a tallow candle]]` means one, for whoever
is acting.

Two verbs rather than one tag carrying a direction, because a direction word is a thing
the model can get subtly wrong, and a missing one would have to be guessed. Which way an
item moved is not a guessable field.

**The posture here is `[[CHECK]]`'s, not `[[CANON]]`'s.** The canon parser bends over
backwards never to lose a fact, because a fact filed under the wrong scope beats a fact
dropped on the floor. This parser drops anything it cannot read cleanly. The asymmetry is
deliberate: a lost canon line costs the ledger a sentence, and a misread item change
writes the model's fiction into the character sheet — which is the exact failure this
module was built to end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dndc.schema.events import InventoryDirection

#: The whole tag, either verb. Non-greedy body so two tags in one reply parse as two.
INVENTORY_PATTERN = re.compile(
    r"\[\[\s*(?P<verb>GAIN|LOSE)\s*:(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL
)

_DIRECTIONS = {"gain": InventoryDirection.GAIN, "lose": InventoryDirection.LOSE}

#: `<character> —` at the head of the body. Only an em/en dash or a double hyphen counts
#: as the separator: a single hyphen and a colon both appear inside ordinary item names
#: ("half-empty waterskin", "note: unsigned"), and splitting on those would silently
#: promote half an item name to a character name.
_WHO = re.compile(r"^\s*(?P<who>[^—–]{1,40}?)\s*(?:[—–]|--)\s*")

#: `×3`, `x3`, `*3`, `(3)`, or a bare trailing `3`, at either end of the item.
_TRAILING_QUANTITY = re.compile(r"[\s,]*[(\[]?\s*(?:[×x*]\s*)?(?P<n>\d{1,4})\s*[)\]]?\s*$")
_LEADING_QUANTITY = re.compile(r"^\s*(?P<n>\d{1,4})\s*[×x*]?\s+")

#: Words in front of an item that are counting, not naming. "a lantern" is one lantern;
#: "the lantern" is the lantern. Neither belongs in the name a sheet is keyed on.
_ARTICLES = re.compile(r"^(?:a|an|the|some|his|her|their|your|my|its)\s+", re.IGNORECASE)

#: Number words the GM reaches for instead of digits. Stops where a sheet stops caring —
#: past a dozen of something, the GM writes the digit.
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "a": 1, "an": 1, "a pair of": 2, "a brace of": 2,
}
_LEADING_NUMBER_WORD = re.compile(
    rf"^(?P<word>{'|'.join(sorted(_NUMBER_WORDS, key=len, reverse=True))})\s+", re.IGNORECASE
)

#: Longest a proposal's item name may be. Past this the GM has narrated a clause into the
#: tag rather than named a thing, and no sheet should carry a sentence.
MAX_ITEM_CHARS = 60


@dataclass(frozen=True)
class InventoryTag:
    """One item change the GM proposed. Nothing has happened yet."""

    item: str
    direction: InventoryDirection
    quantity: int = 1
    #: Who the GM named, verbatim. `None` means it did not say, and the acting character
    #: is meant — resolving that needs the party, which this module does not have.
    character: str | None = None
    raw: str = ""

    @property
    def verb(self) -> str:
        return "gains" if self.direction is InventoryDirection.GAIN else "loses"

    def render(self) -> str:
        """One line for the confirmation prompt."""
        count = f" ×{self.quantity}" if self.quantity > 1 else ""
        return f"{self.character or 'you'} {self.verb} {self.item}{count}"


def find_inventory_tags(text: str) -> list[InventoryTag]:
    """Every item change the GM proposed, in the order it proposed them."""
    tags = []
    for match in INVENTORY_PATTERN.finditer(text):
        tag = _parse_body(
            match.group("body"), verb=match.group("verb"), raw=match.group(0)
        )
        if tag is not None:
            tags.append(tag)
    return tags


def strip_inventory_tags(text: str) -> str:
    """The narration without the tags, for the screen and the recent window.

    Same reason as the other two strippers: a tag left in the window comes back to the GM
    as its own past voice, and it learns to narrate in tags.
    """
    return _tidy(INVENTORY_PATTERN.sub("", text))


def _tidy(text: str) -> str:
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse_body(body: str, verb: str, raw: str) -> InventoryTag | None:
    who_match = _WHO.match(body)
    character = None
    remainder = body
    if who_match is not None:
        character = who_match.group("who").strip() or None
        remainder = body[who_match.end():]

    item, quantity = _split_quantity(remainder)
    if not item or len(item) > MAX_ITEM_CHARS:
        return None
    return InventoryTag(
        item=item,
        direction=_DIRECTIONS[verb.lower()],
        quantity=quantity,
        character=character,
        raw=raw,
    )


def _split_quantity(text: str) -> tuple[str, int]:
    """Pull a count off either end of the item name.

    Digits win over number words, and a trailing count wins over a leading one, because
    `2 flasks x3` is a model confusing itself and the explicit multiplier is the later,
    more deliberate statement.
    """
    item = text.strip()
    quantity = 1

    trailing = _TRAILING_QUANTITY.search(item)
    if trailing is not None and trailing.start() > 0:
        quantity = int(trailing.group("n"))
        item = item[: trailing.start()].strip()

    leading = _LEADING_QUANTITY.match(item)
    if leading is not None:
        if quantity == 1:
            quantity = int(leading.group("n"))
        item = item[leading.end():].strip()
    else:
        word = _LEADING_NUMBER_WORD.match(item)
        if word is not None:
            counted = _NUMBER_WORDS[word.group("word").lower()]
            # An article is only a count when nothing else said otherwise: "a pair of
            # boots x2" is two pairs, not one.
            if quantity == 1:
                quantity = counted
            item = item[word.end():].strip()

    item = _ARTICLES.sub("", item).strip(" .,;:")
    return item, max(quantity, 1)
