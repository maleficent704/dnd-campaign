"""Working out who a name means.

Shared by `/switch` (P1.5), `/inventory` and the P2.4 item store, which is why it is here
rather than in the CLI: three callers with one matching policy beats three policies. The
protocol is `.name` and `.player`, so it works on a `PartyMember` (what the prompt sees)
and a `CharacterSheet` (what the engine resolves against) alike.
"""

from __future__ import annotations

from typing import Protocol, Sequence, TypeVar


class Named(Protocol):
    name: str
    player: str


T = TypeVar("T", bound=Named)


def resolve_member(query: str, party: Sequence[T]) -> list[T]:
    """Who a player could mean by `query` — narrowest reading first.

    At a table you say "Corin", not "Corin Vale", and the first two-player session hit
    exactly that: `/switch corin` was rejected because the lookup was an exact full-name
    match. Matching runs in tiers — full name, then a single name out of the full one,
    then a prefix — and stops at the first tier that hits, so a unique first name is
    never made ambiguous by some longer name it happens to prefix.

    Player names match too. "Sam's turn" is as natural a thing to say as the character's
    name, and character names are tried first, so a collision resolves toward the
    character.

    Returns every candidate: none means unknown, more than one means genuinely ambiguous
    and the caller should say so rather than pick.
    """
    wanted = query.strip().casefold()
    if not wanted:
        return []

    def whole(member: T, field: str) -> str:
        return getattr(member, field).casefold()

    def words(member: T, field: str) -> tuple[str, ...]:
        return tuple(whole(member, field).split())

    tiers = (
        lambda member, field: whole(member, field) == wanted,
        lambda member, field: wanted in words(member, field),
        lambda member, field: whole(member, field).startswith(wanted)
        or any(word.startswith(wanted) for word in words(member, field)),
    )
    for matches in tiers:
        for field in ("name", "player"):
            found = [member for member in party if matches(member, field)]
            if found:
                return found
    return []
