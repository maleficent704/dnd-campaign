"""Normalize the pinned raw SRD dataset into typed models.

Upstream shape is an API dump: cross-references are `{index, name, url}` objects and
several fields are stringly-typed ("30 ft."). Everything here exists to turn that into
something the deterministic core can use without re-parsing prose at runtime.

Two rules this module holds to:

* **Fail loudly.** A field we do not recognise is an error, not a silent drop. Ingestion
  runs offline, on data we control the version of; if it changes shape we want to know
  at ingest time rather than mid-combat.
* **Deterministic output.** Collections are sorted by index, so a re-run over unchanged
  input produces byte-identical files. That is what makes the pin verifiable.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dndc.schema.sheet import Ability, AbilityScores
from dndc.schema.srd import (
    AreaOfEffect,
    ArmorProfile,
    CharacterClass,
    ClassLevel,
    Condition,
    Cost,
    Equipment,
    IngestScope,
    Monster,
    MonsterAction,
    MonsterDamage,
    ProficiencyChoice,
    Size,
    Species,
    SpellDamage,
    Spell,
    SRDData,
    Subspecies,
    WeaponProfile,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW_ROOT = _REPO_ROOT / "data" / "srd" / "raw" / "2014" / "en"
DEFAULT_NORMALIZED_ROOT = _REPO_ROOT / "data" / "srd" / "normalized"
DEFAULT_SOURCE_MANIFEST = _REPO_ROOT / "data" / "srd" / "SOURCE.json"

#: Upstream filenames, by the collection they feed.
RAW_FILES = {
    "races": "5e-SRD-Races.json",
    "subraces": "5e-SRD-Subraces.json",
    "classes": "5e-SRD-Classes.json",
    "levels": "5e-SRD-Levels.json",
    "spells": "5e-SRD-Spells.json",
    "monsters": "5e-SRD-Monsters.json",
    "equipment": "5e-SRD-Equipment.json",
    "conditions": "5e-SRD-Conditions.json",
}

_FEET_RE = re.compile(r"(\d+)")
#: Upstream placeholder for the caster's spellcasting ability modifier ("1d8 + MOD").
_MOD_RE = re.compile(r"\s*\+\s*MOD\s*$")


class SRDIngestError(ValueError):
    """Raised when the raw dataset is missing, malformed, or an unexpected shape."""


# --- small helpers ---------------------------------------------------------


def _ref(obj: Any) -> str | None:
    """Flatten an upstream `{index, name, url}` reference to its index."""
    if not isinstance(obj, dict):
        return None
    index = obj.get("index")
    return index if isinstance(index, str) else None


def _refs(items: Any) -> tuple[str, ...]:
    if not isinstance(items, list):
        return ()
    return tuple(i for i in (_ref(o) for o in items) if i is not None)


def _ability(obj: Any) -> Ability | None:
    index = _ref(obj)
    try:
        return Ability(index) if index else None
    except ValueError:
        return None


def _size(value: Any, *, what: str) -> Size:
    try:
        return Size(value)
    except ValueError as exc:
        raise SRDIngestError(f"{what}: unknown size {value!r}") from exc


def _feet(value: Any) -> int:
    """'30 ft.' -> 30. Upstream stores movement and sense ranges as prose."""
    if isinstance(value, (int, float)):
        return int(value)
    match = _FEET_RE.search(str(value))
    return int(match.group(1)) if match else 0


def _int_keys(mapping: Any) -> dict[int, str]:
    """Upstream keys per-slot-level maps with string keys."""
    if not isinstance(mapping, dict):
        return {}
    return {int(k): str(v) for k, v in mapping.items()}


def _strip_mod(mapping: dict[int, str], *, what: str) -> tuple[dict[int, str], bool]:
    """Split "1d8 + MOD" into a rollable "1d8" and a flag.

    Mixed usage within one spell would mean the placeholder means something we have not
    understood, so it is an error rather than a guess.
    """
    stripped, flags = {}, set()
    for level, expression in mapping.items():
        cleaned = _MOD_RE.sub("", expression)
        flags.add(cleaned != expression)
        stripped[level] = cleaned
    if len(flags) > 1:
        raise SRDIngestError(f"{what}: some amounts use the MOD placeholder and some do not")
    return stripped, flags.pop() if flags else False


def _texts(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(v) for v in value)
    return ()


# --- per-collection normalizers -------------------------------------------


def _ability_bonuses(raw: Any) -> dict[Ability, int]:
    bonuses: dict[Ability, int] = {}
    for entry in raw or []:
        ability = _ability(entry.get("ability_score"))
        if ability is not None:
            bonuses[ability] = int(entry.get("bonus", 0))
    return bonuses


def normalize_species(raw: list[dict]) -> dict[str, Species]:
    out = {}
    for r in raw:
        out[r["index"]] = Species(
            index=r["index"],
            name=r["name"],
            speed=int(r.get("speed", 30)),
            size=_size(r.get("size"), what=f"species {r['index']}"),
            ability_bonuses=_ability_bonuses(r.get("ability_bonuses")),
            languages=_refs(r.get("languages")),
            traits=_refs(r.get("traits")),
            subspecies=_refs(r.get("subraces")),
            age=r.get("age", ""),
            alignment=r.get("alignment", ""),
            size_description=r.get("size_description", ""),
            language_description=r.get("language_desc", ""),
        )
    return dict(sorted(out.items()))


def normalize_subspecies(raw: list[dict]) -> dict[str, Subspecies]:
    out = {}
    for r in raw:
        species = _ref(r.get("race"))
        if species is None:
            raise SRDIngestError(f"subspecies {r['index']}: no parent species")
        out[r["index"]] = Subspecies(
            index=r["index"],
            name=r["name"],
            species=species,
            description=r.get("desc", ""),
            ability_bonuses=_ability_bonuses(r.get("ability_bonuses")),
            traits=_refs(r.get("racial_traits")),
        )
    return dict(sorted(out.items()))


def _proficiency_choices(raw: Any) -> tuple[ProficiencyChoice, ...]:
    choices = []
    for c in raw or []:
        source = c.get("from", {})
        options = []
        for opt in source.get("options", []) or []:
            index = _ref(opt.get("item"))
            if index is not None:
                options.append(index)
        choices.append(
            ProficiencyChoice(
                description=c.get("desc", ""),
                choose=int(c.get("choose", 1)),
                options=tuple(options),
            )
        )
    return tuple(choices)


def _class_level(raw: dict) -> ClassLevel:
    spellcasting = raw.get("spellcasting") or {}
    slots = {}
    for key, value in spellcasting.items():
        if key.startswith("spell_slots_level_") and value:
            slots[int(key.rsplit("_", 1)[1])] = int(value)
    return ClassLevel(
        level=int(raw["level"]),
        proficiency_bonus=int(raw["prof_bonus"]),
        features=_refs(raw.get("features")),
        ability_score_bonuses=int(raw.get("ability_score_bonuses", 0)),
        spell_slots=dict(sorted(slots.items())),
        cantrips_known=spellcasting.get("cantrips_known"),
        spells_known=spellcasting.get("spells_known"),
        class_specific=raw.get("class_specific") or {},
    )


def normalize_classes(
    raw_classes: list[dict], raw_levels: list[dict], scope: IngestScope
) -> dict[str, CharacterClass]:
    # Subclass levels live in the same file and carry a "subclass" key; they must not be
    # folded into the class progression (they also lack prof_bonus, so this is load-bearing).
    by_class: dict[str, dict[int, ClassLevel]] = {}
    for entry in raw_levels:
        if entry.get("subclass") is not None:
            continue
        class_index = _ref(entry.get("class"))
        level = int(entry["level"])
        if class_index is None or level > scope.max_class_level:
            continue
        by_class.setdefault(class_index, {})[level] = _class_level(entry)

    out = {}
    for r in raw_classes:
        index = r["index"]
        spellcasting = r.get("spellcasting") or {}
        starting = []
        for item in r.get("starting_equipment", []) or []:
            equipment = _ref(item.get("equipment"))
            if equipment is not None:
                starting.append(equipment)
        out[index] = CharacterClass(
            index=index,
            name=r["name"],
            hit_die=int(r["hit_die"]),
            saving_throws=tuple(
                a for a in (_ability(s) for s in r.get("saving_throws", [])) if a is not None
            ),
            proficiencies=_refs(r.get("proficiencies")),
            proficiency_choices=_proficiency_choices(r.get("proficiency_choices")),
            starting_equipment=tuple(starting),
            spellcasting_ability=_ability(spellcasting.get("spellcasting_ability")),
            subclasses=_refs(r.get("subclasses")),
            levels=dict(sorted(by_class.get(index, {}).items())),
        )
    return dict(sorted(out.items()))


def normalize_spells(raw: list[dict]) -> dict[str, Spell]:
    out = {}
    for r in raw:
        uses_modifier = False
        damage = None
        if raw_damage := r.get("damage"):
            by_slot, slot_mod = _strip_mod(
                _int_keys(raw_damage.get("damage_at_slot_level")), what=f"spell {r['index']}"
            )
            by_character, character_mod = _strip_mod(
                _int_keys(raw_damage.get("damage_at_character_level")),
                what=f"spell {r['index']}",
            )
            uses_modifier = slot_mod or character_mod
            damage = SpellDamage(
                damage_type=_ref(raw_damage.get("damage_type")),
                at_slot_level=by_slot,
                at_character_level=by_character,
            )
        healing, healing_mod = _strip_mod(
            _int_keys(r.get("heal_at_slot_level")), what=f"spell {r['index']}"
        )
        uses_modifier = uses_modifier or healing_mod
        aoe = None
        if raw_aoe := r.get("area_of_effect"):
            aoe = AreaOfEffect(type=raw_aoe["type"], size=int(raw_aoe["size"]))
        out[r["index"]] = Spell(
            index=r["index"],
            name=r["name"],
            level=int(r["level"]),
            school=_ref(r.get("school")) or "",
            casting_time=r.get("casting_time", ""),
            range=r.get("range", ""),
            duration=r.get("duration", ""),
            components=tuple(r.get("components", []) or []),
            material=r.get("material"),
            ritual=bool(r.get("ritual", False)),
            concentration=bool(r.get("concentration", False)),
            description=_texts(r.get("desc")),
            higher_level=_texts(r.get("higher_level")),
            classes=_refs(r.get("classes")),
            subclasses=_refs(r.get("subclasses")),
            attack_type=r.get("attack_type"),
            save_ability=_ability((r.get("dc") or {}).get("dc_type")),
            damage=damage,
            area_of_effect=aoe,
            heal_at_slot_level=healing,
            adds_spellcasting_modifier=uses_modifier,
        )
    return dict(sorted(out.items()))


def _monster_actions(raw: Any) -> tuple[MonsterAction, ...]:
    actions = []
    for a in raw or []:
        damages = []
        for d in a.get("damage", []) or []:
            # Choice-style damage entries carry a "from" block instead of dice; the dice
            # live inside the options and are narrative-only for our purposes.
            if not isinstance(d, dict) or "damage_dice" not in d:
                continue
            damages.append(
                MonsterDamage(
                    damage_dice=d.get("damage_dice", ""),
                    damage_type=_ref(d.get("damage_type")),
                )
            )
        dc = a.get("dc") or {}
        actions.append(
            MonsterAction(
                name=a["name"],
                description=a.get("desc", ""),
                attack_bonus=a.get("attack_bonus"),
                damage=tuple(damages),
                usage=a.get("usage") or {},
                dc_ability=_ability(dc.get("dc_type")),
                dc_value=dc.get("dc_value"),
            )
        )
    return tuple(actions)


def normalize_monsters(raw: list[dict], scope: IngestScope) -> dict[str, Monster]:
    out = {}
    for r in raw:
        cr = float(r.get("challenge_rating", 0))
        if cr > scope.max_challenge_rating:
            continue
        ac_entries = r.get("armor_class") or []
        if not ac_entries:
            raise SRDIngestError(f"monster {r['index']}: no armor class")
        primary_ac = ac_entries[0]

        speed = {}
        can_hover = False
        for mode, value in (r.get("speed") or {}).items():
            if mode == "hover":
                can_hover = bool(value)
                continue
            speed[mode] = _feet(value)

        raw_senses = r.get("senses") or {}
        senses = {k: str(v) for k, v in raw_senses.items() if k != "passive_perception"}

        proficiencies = {}
        for p in r.get("proficiencies", []) or []:
            index = _ref(p.get("proficiency"))
            if index is not None:
                proficiencies[index] = int(p.get("value", 0))

        out[r["index"]] = Monster(
            index=r["index"],
            name=r["name"],
            size=_size(r.get("size"), what=f"monster {r['index']}"),
            type=r.get("type", ""),
            subtype=r.get("subtype"),
            alignment=r.get("alignment", ""),
            armor_class=int(primary_ac.get("value", 10)),
            armor_class_kind=primary_ac.get("type", ""),
            hit_points=int(r["hit_points"]),
            hit_dice=r.get("hit_dice", ""),
            speed=dict(sorted(speed.items())),
            can_hover=can_hover,
            abilities=AbilityScores.model_validate(
                {
                    "str": r["strength"],
                    "dex": r["dexterity"],
                    "con": r["constitution"],
                    "int": r["intelligence"],
                    "wis": r["wisdom"],
                    "cha": r["charisma"],
                }
            ),
            challenge_rating=cr,
            proficiency_bonus=int(r["proficiency_bonus"]),
            xp=int(r.get("xp", 0)),
            proficiencies=dict(sorted(proficiencies.items())),
            damage_vulnerabilities=tuple(r.get("damage_vulnerabilities", []) or []),
            damage_resistances=tuple(r.get("damage_resistances", []) or []),
            damage_immunities=tuple(r.get("damage_immunities", []) or []),
            condition_immunities=_refs(r.get("condition_immunities")),
            senses=dict(sorted(senses.items())),
            passive_perception=int(raw_senses.get("passive_perception", 10)),
            languages=r.get("languages", ""),
            description=" ".join(_texts(r.get("desc"))),
            special_abilities=_monster_actions(r.get("special_abilities")),
            actions=_monster_actions(r.get("actions")),
            legendary_actions=_monster_actions(r.get("legendary_actions")),
            reactions=_monster_actions(r.get("reactions")),
        )
    return dict(sorted(out.items()))


def normalize_equipment(raw: list[dict]) -> dict[str, Equipment]:
    out = {}
    for r in raw:
        weapon = None
        if r.get("weapon_category"):
            damage = r.get("damage") or {}
            two_handed = r.get("two_handed_damage") or {}
            rng = r.get("range") or {}
            throw = r.get("throw_range") or {}
            weapon = WeaponProfile(
                category=r.get("weapon_category", ""),
                weapon_range=r.get("weapon_range", ""),
                damage_dice=damage.get("damage_dice", ""),
                damage_type=_ref(damage.get("damage_type")),
                two_handed_damage_dice=two_handed.get("damage_dice"),
                properties=_refs(r.get("properties")),
                range_normal=rng.get("normal"),
                range_long=rng.get("long"),
                throw_range_normal=throw.get("normal"),
                throw_range_long=throw.get("long"),
            )
        armor = None
        if r.get("armor_category"):
            ac = r.get("armor_class") or {}
            armor = ArmorProfile(
                category=r.get("armor_category", ""),
                base_ac=int(ac.get("base", 10)),
                dex_bonus=bool(ac.get("dex_bonus", False)),
                max_dex_bonus=ac.get("max_bonus"),
                strength_minimum=int(r.get("str_minimum", 0)),
                stealth_disadvantage=bool(r.get("stealth_disadvantage", False)),
            )
        cost = r.get("cost") or {}
        out[r["index"]] = Equipment(
            index=r["index"],
            name=r["name"],
            category=_ref(r.get("equipment_category")) or "",
            cost=Cost(quantity=int(cost.get("quantity", 0)), unit=cost.get("unit", "")),
            weight=float(r.get("weight") or 0.0),
            description=_texts(r.get("desc")),
            weapon=weapon,
            armor=armor,
        )
    return dict(sorted(out.items()))


def normalize_conditions(raw: list[dict]) -> dict[str, Condition]:
    return dict(
        sorted(
            (
                r["index"],
                Condition(index=r["index"], name=r["name"], description=_texts(r.get("desc"))),
            )
            for r in raw
        )
    )


# --- top level -------------------------------------------------------------


def load_raw(raw_root: Path = DEFAULT_RAW_ROOT) -> dict[str, list[dict]]:
    """Read the vendored upstream JSON files."""
    raw = {}
    for key, filename in RAW_FILES.items():
        path = raw_root / filename
        if not path.exists():
            raise SRDIngestError(
                f"missing raw SRD file: {path}. The pinned dataset should be committed "
                f"under data/srd/raw/ — see data/srd/ATTRIBUTION.md."
            )
        try:
            raw[key] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SRDIngestError(f"{path} is not valid JSON: {exc}") from exc
    return raw


def normalize(raw: dict[str, list[dict]], scope: IngestScope | None = None) -> SRDData:
    """Turn the raw upstream dump into the typed dataset. Pure; no I/O."""
    scope = scope or IngestScope()
    return SRDData(
        scope=scope,
        species=normalize_species(raw["races"]),
        subspecies=normalize_subspecies(raw["subraces"]),
        classes=normalize_classes(raw["classes"], raw["levels"], scope),
        spells=normalize_spells(raw["spells"]),
        monsters=normalize_monsters(raw["monsters"], scope),
        equipment=normalize_equipment(raw["equipment"]),
        conditions=normalize_conditions(raw["conditions"]),
    )


@dataclass(frozen=True)
class IngestReport:
    counts: dict[str, int]
    scope: IngestScope
    output_root: Path
    issues: list[str] = field(default_factory=list)


def ingest(
    raw_root: Path = DEFAULT_RAW_ROOT,
    output_root: Path = DEFAULT_NORMALIZED_ROOT,
    scope: IngestScope | None = None,
) -> IngestReport:
    """Read raw -> normalize -> validate -> write. Output is gitignored (OD-7)."""
    from dndc.srd.validate import validate_dataset

    data = normalize(load_raw(raw_root), scope)
    issues = [str(i) for i in validate_dataset(data)]

    output_root.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump(mode="json")
    for collection in ("species", "subspecies", "classes", "spells", "monsters",
                       "equipment", "conditions"):
        target = output_root / f"{collection}.json"
        target.write_text(
            json.dumps(payload[collection], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    manifest = {
        "generated_from": str(raw_root),
        "scope": data.scope.model_dump(mode="json"),
        "counts": data.counts(),
        "validation_issues": issues,
        "note": "Regenerated by `dndc srd ingest`. Never commit this directory (OD-7).",
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return IngestReport(
        counts=data.counts(), scope=data.scope, output_root=output_root, issues=issues
    )


def verify_pin(
    manifest_path: Path = DEFAULT_SOURCE_MANIFEST,
    srd_root: Path | None = None,
) -> list[str]:
    """Re-hash the vendored raw files against SOURCE.json.

    The pin is only worth something if drift is detectable, so this is a real check
    rather than a comment in the attribution file.
    """
    if not manifest_path.exists():
        return [f"missing pin manifest: {manifest_path}"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = srd_root or manifest_path.parent
    problems = []
    for relative, expected in sorted(manifest.get("files", {}).items()):
        path = root / relative
        if not path.exists():
            problems.append(f"{relative}: missing")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected["sha256"]:
            problems.append(
                f"{relative}: sha256 mismatch "
                f"(expected {expected['sha256'][:12]}…, got {actual[:12]}…)"
            )
    return problems
