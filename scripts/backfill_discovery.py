"""One-time backfill for the discovery axis (D-008 item 30), authorised by Fable's
P6.2 (h) ruling: "backfill of The Salt Road's six facts may ride with the implementation".

Not a general migration and deliberately not written as one. `character` scope is decided
by rule — a co-creation backstory fact is known to the player who wrote it, with no session
behind it because there was no moment of finding out. Every `world` fact is decided by an
explicit id, hand-audited against the 2026-09-03 (h) entry, because "the party knows this"
is not a property a script can read off a row. An id not listed here is left undiscovered,
which is the safe direction.

Idempotent: an entry that already carries the axis is left exactly as it is.
"""
import io
import sys

import yaml

# The Salt Road's six world facts, each verified against the (h) entry and the session-1
# log: the party found the gap in the straw, watched the accusation happen, and are
# standing in the town. `discovered_in` is the session they were established in, which for
# these six is also the session they were witnessed in.
FOUND_IN_PLAY = {
    "the-salt-road": {
        "world-brakewater",
        "world-caravan",
        "world-missing-crate",
        "world-accusation",
        "world-third-wagon",
        "world-caravan-master",
    },
}


def backfill(path: str, campaign: str) -> tuple[int, int]:
    data = yaml.safe_load(io.open(path, encoding="utf-8").read()) or {}
    entries = data.get("entries") or []
    known_ids = FOUND_IN_PLAY.get(campaign, set())
    seen_ids = {entry["id"] for entry in entries}
    missing = known_ids - seen_ids
    if missing:
        raise SystemExit(f"{campaign}: named ids not in the ledger: {sorted(missing)}")

    changed = 0
    for entry in entries:
        if entry.get("discovered"):
            continue
        if entry.get("scope") == "character":
            entry["discovered"] = True
            changed += 1
        elif entry["id"] in known_ids:
            entry["discovered"] = True
            entry["discovered_in"] = entry.get("session")
            changed += 1
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    )
    return changed, len(entries)


if __name__ == "__main__":
    path, campaign = sys.argv[1], sys.argv[2]
    changed, total = backfill(path, campaign)
    print(f"{campaign}: {changed} of {total} entries marked discovered")
