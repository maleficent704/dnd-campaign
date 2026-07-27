"""P0.2: SRD ingestion, normalization, validation, and lookup.

Logic is tested against hand-built fixtures so the suite stays fast and independent of
the vendored 4 MB dataset. A separate section then runs the *real* pinned data through
ingestion — that is the check that catches upstream shape drift, and it is worth the
second or so it costs. Nothing here touches the network.
"""

from __future__ import annotations

import json

import pytest

from dndc.rules import dice
from dndc.schema.sheet import Ability
from dndc.schema.srd import IngestScope, Size, SRDData
from dndc.srd.ingest import (
    DEFAULT_RAW_ROOT,
    RAW_FILES,
    SRDIngestError,
    ingest,
    load_raw,
    normalize,
    normalize_classes,
    normalize_conditions,
    normalize_equipment,
    normalize_monsters,
    normalize_spells,
    normalize_species,
    verify_pin,
)
from dndc.srd.repository import SRDRepository, load_dataset
from dndc.srd.validate import validate_dataset


def ref(index: str, name: str | None = None) -> dict:
    return {"index": index, "name": name or index.title(), "url": f"/api/2014/x/{index}"}


# --- fixtures --------------------------------------------------------------


RAW_SPECIES = [
    {
        "index": "dwarf",
        "name": "Dwarf",
        "speed": 25,
        "size": "Medium",
        "ability_bonuses": [{"ability_score": ref("con", "CON"), "bonus": 2}],
        "languages": [ref("common"), ref("dwarvish")],
        "traits": [ref("darkvision")],
        "subraces": [ref("hill-dwarf")],
        "age": "Dwarves mature at the same rate as humans.",
        "alignment": "Most dwarves are lawful.",
        "size_description": "Between 4 and 5 feet tall.",
        "language_desc": "You speak Common and Dwarvish.",
    }
]

RAW_SUBSPECIES = [
    {
        "index": "hill-dwarf",
        "name": "Hill Dwarf",
        "race": ref("dwarf"),
        "desc": "As a hill dwarf, you have keen senses.",
        "ability_bonuses": [{"ability_score": ref("wis", "WIS"), "bonus": 1}],
        "racial_traits": [ref("dwarven-toughness")],
    }
]

RAW_CLASSES = [
    {
        "index": "wizard",
        "name": "Wizard",
        "hit_die": 6,
        "saving_throws": [ref("int", "INT"), ref("wis", "WIS")],
        "proficiencies": [ref("daggers")],
        "proficiency_choices": [
            {
                "desc": "Choose two from ...",
                "choose": 2,
                "from": {
                    "options": [
                        {"item": ref("skill-arcana")},
                        {"item": ref("skill-history")},
                    ]
                },
            }
        ],
        "starting_equipment": [{"equipment": ref("spellbook"), "quantity": 1}],
        "spellcasting": {"spellcasting_ability": ref("int", "INT")},
        "subclasses": [ref("evocation")],
    }
]


def raw_levels(class_index: str = "wizard", up_to: int = 6) -> list[dict]:
    levels = []
    for level in range(1, up_to + 1):
        levels.append(
            {
                "level": level,
                "prof_bonus": 2 + (level - 1) // 4,
                "ability_score_bonuses": 1 if level == 4 else 0,
                "features": [ref(f"feature-{level}")],
                "class_specific": {"arcane_recovery_levels": level // 2},
                "index": f"{class_index}-{level}",
                "class": ref(class_index),
                "spellcasting": {
                    "cantrips_known": 3,
                    "spells_known": 4,
                    "spell_slots_level_1": 2,
                    "spell_slots_level_2": 0,
                },
            }
        )
    # A subclass level entry: same file, no prof_bonus, must never be merged in.
    levels.append(
        {
            "level": 3,
            "features": [ref("evocation-savant")],
            "index": f"{class_index}-3-evocation",
            "class": ref(class_index),
            "subclass": ref("evocation"),
        }
    )
    return levels


RAW_SPELLS = [
    {
        "index": "cure-wounds",
        "name": "Cure Wounds",
        "level": 1,
        "school": ref("evocation"),
        "casting_time": "1 action",
        "range": "Touch",
        "duration": "Instantaneous",
        "components": ["V", "S"],
        "ritual": False,
        "concentration": False,
        "desc": ["A creature you touch regains hit points."],
        "classes": [ref("wizard")],
        "subclasses": [],
        "heal_at_slot_level": {"1": "1d8 + MOD", "2": "2d8 + MOD"},
    },
    {
        "index": "fire-bolt",
        "name": "Fire Bolt",
        "level": 0,
        "school": ref("evocation"),
        "casting_time": "1 action",
        "range": "120 feet",
        "duration": "Instantaneous",
        "components": ["V", "S"],
        "ritual": False,
        "concentration": False,
        "desc": ["You hurl a mote of fire."],
        "classes": [ref("wizard")],
        "subclasses": [],
        "attack_type": "ranged",
        "damage": {
            "damage_type": ref("fire"),
            "damage_at_character_level": {"1": "1d10", "5": "2d10"},
        },
    },
    {
        "index": "fireball",
        "name": "Fireball",
        "level": 3,
        "school": ref("evocation"),
        "casting_time": "1 action",
        "range": "150 feet",
        "duration": "Instantaneous",
        "components": ["V", "S", "M"],
        "material": "A tiny ball of bat guano.",
        "ritual": False,
        "concentration": False,
        "desc": ["A bright streak flashes."],
        "classes": [ref("wizard")],
        "subclasses": [],
        "dc": {"dc_type": ref("dex", "DEX"), "dc_success": "half"},
        "area_of_effect": {"type": "sphere", "size": 20},
        "damage": {
            "damage_type": ref("fire"),
            "damage_at_slot_level": {"3": "8d6", "4": "9d6"},
        },
    },
]

RAW_MONSTERS = [
    {
        "index": "goblin",
        "name": "Goblin",
        "size": "Small",
        "type": "humanoid",
        "subtype": "goblinoid",
        "alignment": "neutral evil",
        "armor_class": [{"type": "armor", "value": 15, "armor": [ref("leather-armor")]}],
        "hit_points": 7,
        "hit_dice": "2d6",
        "speed": {"walk": "30 ft."},
        "strength": 8,
        "dexterity": 14,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 8,
        "charisma": 8,
        "proficiencies": [{"value": 6, "proficiency": ref("skill-stealth")}],
        "damage_vulnerabilities": [],
        "damage_resistances": [],
        "damage_immunities": [],
        "condition_immunities": [ref("blinded")],
        "senses": {"darkvision": "60 ft.", "passive_perception": 9},
        "languages": "Common, Goblin",
        "challenge_rating": 0.25,
        "proficiency_bonus": 2,
        "xp": 50,
        "actions": [
            {
                "name": "Scimitar",
                "desc": "Melee Weapon Attack: +4 to hit.",
                "attack_bonus": 4,
                "damage": [{"damage_type": ref("slashing"), "damage_dice": "1d6+2"}],
            }
        ],
    },
    {
        "index": "adult-red-dragon",
        "name": "Adult Red Dragon",
        "size": "Huge",
        "type": "dragon",
        "alignment": "chaotic evil",
        "armor_class": [{"type": "natural", "value": 19}],
        "hit_points": 256,
        "hit_dice": "19d12",
        "speed": {"walk": "40 ft.", "fly": "80 ft.", "hover": True},
        "strength": 27,
        "dexterity": 10,
        "constitution": 25,
        "intelligence": 16,
        "wisdom": 13,
        "charisma": 21,
        "proficiencies": [],
        "damage_vulnerabilities": [],
        "damage_resistances": [],
        "damage_immunities": ["fire"],
        "condition_immunities": [],
        "senses": {"blindsight": "60 ft.", "passive_perception": 23},
        "languages": "Common, Draconic",
        "challenge_rating": 17,
        "proficiency_bonus": 6,
        "xp": 18000,
        "actions": [],
    },
]

RAW_EQUIPMENT = [
    {
        "index": "longsword",
        "name": "Longsword",
        "equipment_category": ref("weapon"),
        "weapon_category": "Martial",
        "weapon_range": "Melee",
        "cost": {"quantity": 15, "unit": "gp"},
        "damage": {"damage_dice": "1d8", "damage_type": ref("slashing")},
        "two_handed_damage": {"damage_dice": "1d10", "damage_type": ref("slashing")},
        "range": {"normal": 5},
        "weight": 3,
        "properties": [ref("versatile")],
    },
    {
        "index": "plate-armor",
        "name": "Plate Armor",
        "equipment_category": ref("armor"),
        "armor_category": "Heavy",
        "armor_class": {"base": 18, "dex_bonus": False},
        "str_minimum": 15,
        "stealth_disadvantage": True,
        "weight": 65,
        "cost": {"quantity": 1500, "unit": "gp"},
    },
    {
        "index": "rope-hempen",
        "name": "Rope, Hempen",
        "equipment_category": ref("adventuring-gear"),
        "cost": {"quantity": 1, "unit": "gp"},
        "weight": 10,
        "desc": ["Rope has 2 hit points."],
    },
]

RAW_CONDITIONS = [
    {"index": "blinded", "name": "Blinded", "desc": ["- A blinded creature can't see."]},
    {"index": "prone", "name": "Prone", "desc": ["- A prone creature's only movement..."]},
]


def raw_bundle(**overrides) -> dict[str, list[dict]]:
    bundle = {
        "races": RAW_SPECIES,
        "subraces": RAW_SUBSPECIES,
        "classes": RAW_CLASSES,
        "levels": raw_levels(),
        "spells": RAW_SPELLS,
        "monsters": RAW_MONSTERS,
        "equipment": RAW_EQUIPMENT,
        "conditions": RAW_CONDITIONS,
    }
    bundle.update(overrides)
    return bundle


@pytest.fixture
def data() -> SRDData:
    return normalize(raw_bundle())


# --- species ---------------------------------------------------------------


def test_species_flattens_references(data):
    dwarf = data.species["dwarf"]
    assert dwarf.speed == 25
    assert dwarf.size is Size.MEDIUM
    assert dwarf.ability_bonuses == {Ability.CON: 2}
    assert dwarf.languages == ("common", "dwarvish")
    assert dwarf.subspecies == ("hill-dwarf",)


def test_species_keeps_flavour_text_for_co_creation(data):
    """D-005: the GM narrates from this during character co-creation."""
    assert data.species["dwarf"].age.startswith("Dwarves mature")


def test_subspecies_links_back_to_its_parent(data):
    assert data.subspecies["hill-dwarf"].species == "dwarf"
    assert data.subspecies["hill-dwarf"].ability_bonuses == {Ability.WIS: 1}


def test_unknown_size_is_an_error_not_a_guess():
    broken = [dict(RAW_SPECIES[0], size="Colossal")]
    with pytest.raises(SRDIngestError, match="unknown size"):
        normalize_species(broken)


# --- classes ---------------------------------------------------------------


def test_class_normalizes_saves_and_spellcasting(data):
    wizard = data.classes["wizard"]
    assert wizard.hit_die == 6
    assert wizard.saving_throws == (Ability.INT, Ability.WIS)
    assert wizard.spellcasting_ability is Ability.INT
    assert wizard.starting_equipment == ("spellbook",)


def test_proficiency_choices_are_preserved_for_the_player(data):
    choice = data.classes["wizard"].proficiency_choices[0]
    assert choice.choose == 2
    assert choice.options == ("skill-arcana", "skill-history")


def test_class_levels_are_trimmed_to_scope(data):
    """Default scope is L1-5; the fixture supplies six levels."""
    assert sorted(data.classes["wizard"].levels) == [1, 2, 3, 4, 5]


def test_scope_widening_is_a_parameter():
    wide = normalize(raw_bundle(), IngestScope(max_class_level=6))
    assert sorted(wide.classes["wizard"].levels) == [1, 2, 3, 4, 5, 6]


def test_subclass_level_entries_are_not_merged_into_class_levels():
    """Subclass rows share the file, lack prof_bonus, and would corrupt L3."""
    classes = normalize_classes(RAW_CLASSES, raw_levels(), IngestScope())
    level_three = classes["wizard"].levels[3]
    assert level_three.proficiency_bonus == 2
    assert level_three.features == ("feature-3",)
    assert "evocation-savant" not in level_three.features


def test_spell_slots_drop_empty_levels(data):
    level_one = data.classes["wizard"].levels[1]
    assert level_one.spell_slots == {1: 2}  # the zeroed level-2 slot is omitted
    assert level_one.cantrips_known == 3


def test_class_specific_counters_survive(data):
    assert data.classes["wizard"].levels[4].class_specific == {"arcane_recovery_levels": 2}
    assert data.classes["wizard"].levels[4].ability_score_bonuses == 1


# --- spells ----------------------------------------------------------------


def test_spell_basics(data):
    fireball = data.spells["fireball"]
    assert fireball.level == 3
    assert fireball.school == "evocation"
    assert fireball.save_ability is Ability.DEX
    assert fireball.area_of_effect.type == "sphere"
    assert fireball.area_of_effect.size == 20
    assert fireball.damage.at_slot_level == {3: "8d6", 4: "9d6"}


def test_cantrip_detection(data):
    assert data.spells["fire-bolt"].is_cantrip
    assert not data.spells["fireball"].is_cantrip


def test_cantrip_scaling_is_keyed_by_character_level(data):
    assert data.spells["fire-bolt"].damage.at_character_level == {1: "1d10", 5: "2d10"}


def test_mod_placeholder_becomes_a_flag_not_a_broken_dice_string(data):
    """'1d8 + MOD' is not rollable; the modifier comes from the sheet instead."""
    cure = data.spells["cure-wounds"]
    assert cure.heal_at_slot_level == {1: "1d8", 2: "2d8"}
    assert cure.adds_spellcasting_modifier is True
    dice.parse(cure.heal_at_slot_level[1])  # must not raise


def test_spells_without_the_placeholder_do_not_set_the_flag(data):
    assert data.spells["fireball"].adds_spellcasting_modifier is False


def test_inconsistent_mod_usage_is_an_error():
    broken = [dict(RAW_SPELLS[0], heal_at_slot_level={"1": "1d8 + MOD", "2": "2d8"})]
    with pytest.raises(SRDIngestError, match="MOD placeholder"):
        normalize_spells(broken)


# --- monsters --------------------------------------------------------------


def test_monster_core_fields(data):
    goblin = data.monsters["goblin"]
    assert goblin.armor_class == 15
    assert goblin.armor_class_kind == "armor"
    assert goblin.hit_points == 7
    assert goblin.challenge_rating == 0.25
    assert goblin.size is Size.SMALL


def test_monster_shares_the_character_sheet_ability_model(data):
    """A PC and a stat block must resolve modifiers through the same code."""
    goblin = data.monsters["goblin"]
    assert goblin.abilities.modifier(Ability.DEX) == 2
    assert goblin.abilities.modifier(Ability.STR) == -1


def test_speed_prose_becomes_numbers(data):
    assert data.monsters["goblin"].speed == {"walk": 30}


def test_hover_is_lifted_out_of_the_speed_map():
    monsters = normalize_monsters(RAW_MONSTERS, IngestScope(max_challenge_rating=20))
    dragon = monsters["adult-red-dragon"]
    assert dragon.speed == {"fly": 80, "walk": 40}
    assert dragon.can_hover is True
    assert "hover" not in dragon.speed


def test_passive_perception_is_split_from_the_senses_map(data):
    goblin = data.monsters["goblin"]
    assert goblin.passive_perception == 9
    assert goblin.senses == {"darkvision": "60 ft."}


def test_monster_actions_carry_rollable_damage(data):
    action = data.monsters["goblin"].actions[0]
    assert action.name == "Scimitar"
    assert action.attack_bonus == 4
    assert action.damage[0].damage_dice == "1d6+2"
    assert action.damage[0].damage_type == "slashing"


def test_monsters_above_the_cr_ceiling_are_excluded(data):
    assert "goblin" in data.monsters
    assert "adult-red-dragon" not in data.monsters  # CR 17, default ceiling is 5


def test_cr_ceiling_is_a_parameter():
    wide = normalize(raw_bundle(), IngestScope(max_challenge_rating=20))
    assert "adult-red-dragon" in wide.monsters


def test_monsters_by_cr_is_sorted_and_inclusive(data):
    assert [m.index for m in data.monsters_by_cr(0, 1)] == ["goblin"]
    assert data.monsters_by_cr(1, 5) == []


def test_missing_armor_class_is_an_error():
    broken = [dict(RAW_MONSTERS[0], armor_class=[])]
    with pytest.raises(SRDIngestError, match="no armor class"):
        normalize_monsters(broken, IngestScope())


# --- equipment -------------------------------------------------------------


def test_weapon_profile(data):
    weapon = data.equipment["longsword"].weapon
    assert weapon.damage_dice == "1d8"
    assert weapon.two_handed_damage_dice == "1d10"
    assert weapon.properties == ("versatile",)
    assert weapon.range_normal == 5
    assert data.equipment["longsword"].armor is None


def test_armor_profile(data):
    armor = data.equipment["plate-armor"].armor
    assert armor.base_ac == 18
    assert armor.dex_bonus is False
    assert armor.strength_minimum == 15
    assert armor.stealth_disadvantage is True


def test_plain_gear_has_neither_profile(data):
    rope = data.equipment["rope-hempen"]
    assert rope.weapon is None and rope.armor is None
    assert rope.description == ("Rope has 2 hit points.",)


def test_cost_normalizes_to_copper(data):
    assert data.equipment["longsword"].cost.in_copper == 1500  # 15 gp
    assert data.equipment["rope-hempen"].cost.in_copper == 100


def test_unknown_cost_unit_is_zero_rather_than_a_wrong_price():
    equipment = normalize_equipment(
        [dict(RAW_EQUIPMENT[2], cost={"quantity": 3, "unit": "zz"})]
    )
    assert equipment["rope-hempen"].cost.in_copper == 0


# --- conditions ------------------------------------------------------------


def test_conditions(data):
    assert data.conditions["blinded"].name == "Blinded"
    assert normalize_conditions(RAW_CONDITIONS)["prone"].description


# --- reference data is immutable -------------------------------------------


def test_srd_records_are_frozen(data):
    with pytest.raises(Exception):
        data.monsters["goblin"].hit_points = 99


# --- validation ------------------------------------------------------------


def test_a_clean_dataset_has_no_issues(data):
    assert validate_dataset(data) == []


def test_empty_collection_is_reported():
    issues = validate_dataset(normalize(raw_bundle(conditions=[])))
    assert any(i.collection == "conditions" and "empty" in i.problem for i in issues)


def test_spell_referencing_an_unknown_class_is_reported():
    broken = [dict(RAW_SPELLS[2], classes=[ref("artificer")])]
    issues = validate_dataset(normalize(raw_bundle(spells=broken)))
    assert any("unknown class 'artificer'" in i.problem for i in issues)


def test_missing_class_level_is_reported():
    issues = validate_dataset(normalize(raw_bundle(levels=raw_levels(up_to=3))))
    assert any("do not cover 1..5" in i.problem for i in issues)


def test_monster_with_an_unknown_condition_immunity_is_reported():
    broken = [dict(RAW_MONSTERS[0], condition_immunities=[ref("bewildered")])]
    issues = validate_dataset(normalize(raw_bundle(monsters=broken)))
    assert any("unknown condition 'bewildered'" in i.problem for i in issues)


def test_species_pointing_at_a_missing_subspecies_is_reported():
    issues = validate_dataset(normalize(raw_bundle(subraces=[])))
    assert any("unknown subspecies 'hill-dwarf'" in i.problem for i in issues)


def test_unrollable_dice_are_caught_at_ingest_time():
    """The whole point: bad dice must fail here, not at the table."""
    broken = [dict(RAW_SPELLS[2], damage={
        "damage_type": ref("fire"),
        "damage_at_slot_level": {"3": "8d6 plus a bit"},
    })]
    issues = validate_dataset(normalize(raw_bundle(spells=broken)))
    assert any("unrollable" in i.problem for i in issues)


def test_monster_damage_dice_are_validated():
    broken = [dict(RAW_MONSTERS[0], actions=[{
        "name": "Scimitar",
        "desc": "",
        "attack_bonus": 4,
        "damage": [{"damage_type": ref("slashing"), "damage_dice": "1d6 + STR"}],
    }])]
    issues = validate_dataset(normalize(raw_bundle(monsters=broken)))
    assert any("unrollable" in i.problem and "Scimitar" in i.problem for i in issues)


# --- repository ------------------------------------------------------------


def test_repository_looks_up_by_index_and_by_name(data):
    repo = SRDRepository(data)
    assert repo.monster("goblin").name == "Goblin"
    assert repo.monster("Goblin").index == "goblin"
    assert repo.spell("Fire Bolt").index == "fire-bolt"


def test_repository_name_lookup_is_case_and_space_insensitive(data):
    """The GM says 'fire bolt'; the data says 'fire-bolt'. That mapping is our job."""
    repo = SRDRepository(data)
    assert repo.spell("  FIRE BOLT ").index == "fire-bolt"


def test_repository_returns_none_for_a_miss(data):
    repo = SRDRepository(data)
    assert repo.monster("tarrasque") is None
    assert repo.spell("wish") is None


def test_repository_covers_every_collection(data):
    repo = SRDRepository(data)
    assert repo.species("Dwarf") is not None
    assert repo.character_class("wizard") is not None
    assert repo.equipment("Longsword") is not None
    assert repo.condition("Blinded") is not None


# --- disk round trip -------------------------------------------------------


def test_ingest_writes_a_loadable_dataset(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    for key, filename in RAW_FILES.items():
        (raw_root / filename).write_text(json.dumps(raw_bundle()[key]), encoding="utf-8")

    out = tmp_path / "normalized"
    report = ingest(raw_root=raw_root, output_root=out)
    assert report.issues == []
    assert report.counts["monsters"] == 1

    restored = load_dataset(out)
    assert restored.monsters["goblin"].hit_points == 7
    assert restored.spells["cure-wounds"].adds_spellcasting_modifier is True
    assert restored.scope.max_class_level == 5


def test_ingest_output_is_deterministic(tmp_path):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    for key, filename in RAW_FILES.items():
        (raw_root / filename).write_text(json.dumps(raw_bundle()[key]), encoding="utf-8")

    first = tmp_path / "a"
    second = tmp_path / "b"
    ingest(raw_root=raw_root, output_root=first)
    ingest(raw_root=raw_root, output_root=second)
    for name in ("monsters.json", "spells.json", "classes.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_missing_raw_data_explains_itself(tmp_path):
    with pytest.raises(SRDIngestError, match="missing raw SRD file"):
        load_raw(tmp_path)


def test_loading_before_ingesting_explains_itself(tmp_path):
    with pytest.raises(SRDIngestError, match="dndc srd ingest"):
        load_dataset(tmp_path)


# --- the pin ---------------------------------------------------------------


def test_verify_pin_detects_tampering(tmp_path):
    payload = b'[{"index": "x"}]\n'
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "thing.json").write_bytes(payload)
    manifest = {
        "files": {
            "raw/thing.json": {
                "sha256": "0" * 64,
                "bytes": len(payload),
            }
        }
    }
    manifest_path = tmp_path / "SOURCE.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    problems = verify_pin(manifest_path)
    assert len(problems) == 1
    assert "sha256 mismatch" in problems[0]


def test_verify_pin_reports_missing_files(tmp_path):
    manifest_path = tmp_path / "SOURCE.json"
    manifest_path.write_text(
        json.dumps({"files": {"raw/gone.json": {"sha256": "0" * 64, "bytes": 1}}}),
        encoding="utf-8",
    )
    assert verify_pin(manifest_path) == ["raw/gone.json: missing"]


# --- the real vendored dataset ---------------------------------------------

pytestmark_real = pytest.mark.skipif(
    not (DEFAULT_RAW_ROOT / "5e-SRD-Monsters.json").exists(),
    reason="vendored SRD data not present",
)


@pytest.fixture(scope="module")
def real() -> SRDData:
    return normalize(load_raw())


@pytestmark_real
def test_real_dataset_ingests_cleanly(real):
    """Upstream shape drift shows up here rather than mid-session."""
    assert validate_dataset(real) == []


@pytestmark_real
def test_real_dataset_has_the_expected_shape(real):
    counts = real.counts()
    assert counts["classes"] == 12
    assert counts["conditions"] == 15
    assert counts["species"] == 9
    assert counts["spells"] > 300
    assert counts["monsters"] > 200


@pytestmark_real
def test_real_wizard_progression_matches_the_srd(real):
    """Spot-check against the printed table — the data is only useful if it is right."""
    wizard = real.classes["wizard"]
    assert wizard.hit_die == 6
    assert wizard.saving_throws == (Ability.INT, Ability.WIS)
    assert wizard.levels[1].spell_slots == {1: 2}
    assert wizard.levels[5].spell_slots == {1: 4, 2: 3, 3: 2}
    assert wizard.levels[5].proficiency_bonus == 3


@pytestmark_real
def test_real_goblin_matches_the_srd(real):
    goblin = real.monsters["goblin"]
    assert (goblin.armor_class, goblin.hit_points, goblin.challenge_rating) == (15, 7, 0.25)
    assert goblin.abilities.modifier(Ability.DEX) == 2
    assert goblin.actions[0].attack_bonus == 4


@pytestmark_real
def test_real_dataset_respects_the_default_scope(real):
    assert all(m.challenge_rating <= 5 for m in real.monsters.values())
    assert all(sorted(c.levels) == [1, 2, 3, 4, 5] for c in real.classes.values())


@pytestmark_real
def test_every_real_dice_expression_is_rollable(real):
    """Cross-check between P0.2 data and the P0.3 engine."""
    assert [i for i in validate_dataset(real) if "unrollable" in i.problem] == []


@pytestmark_real
def test_the_vendored_pin_is_intact():
    assert verify_pin() == []
