"""Read access to the normalized SRD.

The engine and the GM prompt builder both go through this, so there is exactly one
answer to "what does the ruleset say". Lookups are case-insensitive on name as well as
index, because the GM will refer to "Fire Bolt" while the data says "fire-bolt", and
resolving that mapping is a data concern rather than something to leave to a model.
"""

from __future__ import annotations

import json
from pathlib import Path

from dndc.schema.srd import (
    Background,
    CharacterClass,
    Condition,
    Equipment,
    Monster,
    Species,
    Spell,
    SRDData,
)
from dndc.srd.ingest import COLLECTIONS, DEFAULT_NORMALIZED_ROOT, SRDIngestError


def load_dataset(root: Path = DEFAULT_NORMALIZED_ROOT) -> SRDData:
    """Load a previously ingested dataset from disk."""
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise SRDIngestError(
            f"no normalized SRD at {root}. Run `dndc srd ingest` first — normalized "
            f"output is generated, not committed (OD-7)."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = {"scope": manifest.get("scope", {})}
    for collection in COLLECTIONS:
        path = root / f"{collection}.json"
        payload[collection] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return SRDData.model_validate(payload)


class SRDRepository:
    """Indexed, case-insensitive access to a loaded dataset."""

    def __init__(self, data: SRDData) -> None:
        self.data = data
        self._by_name = {
            "species": _name_index(data.species),
            "classes": _name_index(data.classes),
            "spells": _name_index(data.spells),
            "monsters": _name_index(data.monsters),
            "equipment": _name_index(data.equipment),
            "backgrounds": _name_index(data.backgrounds),
            "conditions": _name_index(data.conditions),
        }

    @classmethod
    def load(cls, root: Path = DEFAULT_NORMALIZED_ROOT) -> SRDRepository:
        return cls(load_dataset(root))

    def _get(self, collection: str, key: str):
        store = getattr(self.data, collection)
        if key in store:
            return store[key]
        index = self._by_name[collection].get(key.strip().casefold())
        return store.get(index) if index else None

    def species(self, key: str) -> Species | None:
        return self._get("species", key)

    def character_class(self, key: str) -> CharacterClass | None:
        return self._get("classes", key)

    def spell(self, key: str) -> Spell | None:
        return self._get("spells", key)

    def monster(self, key: str) -> Monster | None:
        return self._get("monsters", key)

    def equipment(self, key: str) -> Equipment | None:
        return self._get("equipment", key)

    def background(self, key: str) -> Background | None:
        """The SRD has one (Acolyte). Anything else the table invents is flavour, and
        resolving to None is the correct answer for it — not an error."""
        return self._get("backgrounds", key)

    def condition(self, key: str) -> Condition | None:
        return self._get("conditions", key)

    def counts(self) -> dict[str, int]:
        return self.data.counts()


def _name_index(store: dict) -> dict[str, str]:
    return {record.name.casefold(): index for index, record in store.items()}
