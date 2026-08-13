"""P2.4 — item changes: the GM proposes, the table confirms, the engine performs.

The first playtest ended with the party carrying things no sheet had heard of (Finding 5,
2026-08-05). Fable ruled items are state, so what is defended here is the boundary, not
the bookkeeping:

* the GM's tag never reaches a sheet without a human saying yes;
* a tag the parser cannot read cleanly is dropped rather than guessed at — the opposite
  of the canon parser's posture, because a wrong guess here writes fiction into state;
* a loss the sheet cannot cover still happens *and is flagged*, because that gap is the
  divergence Finding 5 was about;
* every proposal is logged whichever way it goes.
"""

from __future__ import annotations

import pytest
from rich.console import Console

from dndc.game.cli import confirm_inventory
from dndc.game.inventory import InventoryStore, describe_change, proposals_for
from dndc.game.turn import TurnEngine
from dndc.gm.context import CampaignContext, PartyMember
from dndc.gm.inventorytag import (
    MAX_ITEM_CHARS,
    InventoryTag,
    find_inventory_tags,
    strip_inventory_tags,
)
from dndc.logging import SessionLog, read_log
from dndc.models.base import GMResponse, Usage
from dndc.models.mock import MockBackend
from dndc.rules.inventory import apply_change, apply_gain, apply_lose
from dndc.schema.events import EventType, InventoryDirection
from dndc.schema.sheet import (
    AbilityScores,
    CharacterSheet,
    HitPoints,
    InventoryItem,
)

GAIN = InventoryDirection.GAIN
LOSE = InventoryDirection.LOSE


def sheet(name: str = "Corin Vale", items=(), **overrides) -> CharacterSheet:
    data = dict(
        name=name,
        player="Kelly",
        species="Human",
        character_class="Rogue",
        level=1,
        abilities=AbilityScores(str=10, dex=16, con=12, int=12, wis=11, cha=14),
        hit_points=HitPoints(maximum=9, current=9),
        armor_class=14,
        inventory=list(items),
    )
    data.update(overrides)
    return CharacterSheet(**data)


def item(name: str, quantity: int = 1) -> InventoryItem:
    return InventoryItem(name=name, quantity=quantity)


def tag(item: str, direction=GAIN, quantity: int = 1, character=None) -> InventoryTag:
    return InventoryTag(
        item=item, direction=direction, quantity=quantity, character=character, raw="[[tag]]"
    )


def answering(monkeypatch, *answers: str) -> None:
    """Drive the confirmation prompt. Runs out loudly rather than hanging."""
    remaining = list(answers)

    def _ask(*args, **kwargs):
        if not remaining:
            raise AssertionError("the prompt asked more times than the test expected")
        return remaining.pop(0)

    monkeypatch.setattr("dndc.game.cli.Prompt.ask", _ask)


def console() -> Console:
    return Console(force_terminal=False, no_color=True)


# --- the tag parser --------------------------------------------------------


def test_the_plain_form_is_one_item_for_whoever_is_acting():
    (found,) = find_inventory_tags("She presses it into your hand. [[GAIN: iron key]]")
    assert (found.item, found.direction, found.quantity, found.character) == (
        "iron key",
        GAIN,
        1,
        None,
    )


def test_both_verbs_parse_and_they_mean_opposite_things():
    found = find_inventory_tags("[[GAIN: a lantern]] [[LOSE: 3 torches]]")
    assert [(f.item, f.direction, f.quantity) for f in found] == [
        ("lantern", GAIN, 1),
        ("torches", LOSE, 3),
    ]


def test_a_named_character_is_kept_verbatim():
    (found,) = find_inventory_tags("[[LOSE: Corin Vale — waterskin]]")
    assert found.character == "Corin Vale" and found.item == "waterskin"


@pytest.mark.parametrize(
    "body,expected",
    [
        ("torches ×3", 3),
        ("torches x3", 3),
        ("torches *3", 3),
        ("torches (3)", 3),
        ("3 torches", 3),
        ("3 × torches", 3),
        ("three torches", 3),
        ("a pair of boots", 2),
        ("torch", 1),
    ],
)
def test_quantity_is_read_off_either_end_in_the_forms_a_model_reaches_for(body, expected):
    (found,) = find_inventory_tags(f"[[GAIN: {body}]]")
    assert found.quantity == expected


def test_an_explicit_multiplier_beats_a_leading_count():
    """`2 flasks x3` is a model contradicting itself; the multiplier is the later and
    more deliberate of the two statements."""
    (found,) = find_inventory_tags("[[GAIN: 2 flasks x3]]")
    assert (found.item, found.quantity) == ("flasks", 3)


def test_the_article_is_not_part_of_the_name():
    """"the rope" and "Rope" must not become two piles on one sheet."""
    (found,) = find_inventory_tags("[[GAIN: the coil of rope]]")
    assert found.item == "coil of rope"


def test_a_hyphenated_item_is_not_split_into_a_character_and_an_item():
    """Only a dash counts as the character separator. A single hyphen lives inside
    ordinary item names, and splitting on it would invent a character."""
    (found,) = find_inventory_tags("[[GAIN: half-empty waterskin]]")
    assert (found.character, found.item) == (None, "half-empty waterskin")


def test_a_tag_naming_no_item_is_dropped_not_guessed_at():
    """The `[[CHECK]]` posture, deliberately not the `[[CANON]]` one — see the module
    docstring in `gm/inventorytag.py`."""
    assert find_inventory_tags("[[GAIN: ]] [[LOSE:   ]]") == []


def test_a_narrated_clause_is_not_an_item_name():
    long_body = "the key she pressed into your palm as the door " + "closed " * 10
    assert len(long_body) > MAX_ITEM_CHARS
    assert find_inventory_tags(f"[[GAIN: {long_body}]]") == []


def test_the_tags_are_stripped_before_anyone_sees_the_narration():
    text = "You pocket the key. [[GAIN: iron key]] The door clicks shut."
    assert strip_inventory_tags(text) == "You pocket the key. The door clicks shut."


def test_stripping_closes_the_gap_the_tag_left():
    assert "  " not in strip_inventory_tags("You take it. [[GAIN: key]] It is warm.")


# --- the rules half --------------------------------------------------------


def test_a_gain_starts_a_stack():
    outcome = apply_gain([], "iron key")
    assert [(i.name, i.quantity) for i in outcome.inventory] == [("iron key", 1)]
    assert outcome.applied


def test_a_gain_of_something_already_carried_adds_to_the_stack():
    outcome = apply_gain([item("torch", 2)], "torch", 3)
    assert [(i.name, i.quantity) for i in outcome.inventory] == [("torch", 5)]


def test_a_stack_keeps_the_spelling_the_sheet_already_had():
    """The GM writes "Rope" this turn and "rope" the next; one pile, not two."""
    outcome = apply_gain([item("Rope, hempen (50 feet)")], "rope, hempen (50 feet)")
    assert [i.name for i in outcome.inventory] == ["Rope, hempen (50 feet)"]
    assert outcome.inventory[0].quantity == 2


def test_singular_and_plural_are_deliberately_not_the_same_item():
    """A matcher loose enough to merge "torch" with "torches" is loose enough to merge
    things that are not the same item, and a wrong merge destroys one of them."""
    outcome = apply_gain([item("torch", 2)], "torches")
    assert len(outcome.inventory) == 2


def test_a_loss_takes_from_the_stack():
    outcome = apply_lose([item("arrow", 20)], "arrow", 3)
    assert [(i.name, i.quantity) for i in outcome.inventory] == [("arrow", 17)]
    assert outcome.applied


def test_losing_the_last_of_something_removes_the_stack():
    outcome = apply_lose([item("arrow", 3), item("bow")], "arrow", 3)
    assert [i.name for i in outcome.inventory] == ["bow"]
    assert outcome.applied


def test_losing_what_the_sheet_never_had_changes_nothing_and_says_so():
    """This is Finding 5 itself — the fiction ran ahead of the state. It is reported,
    not silently absorbed and not raised as an error."""
    outcome = apply_lose([item("bow")], "lantern")
    assert [i.name for i in outcome.inventory] == ["bow"]
    assert not outcome.applied and outcome.note == "not on the sheet"
    assert outcome.changed == 0


def test_losing_more_than_is_carried_empties_the_stack_and_flags_the_mismatch():
    """Leaving phantom arrows behind because the narration was ahead of the sheet is the
    worse failure; the flag is what stops it being invisible."""
    outcome = apply_lose([item("arrow", 2)], "arrow", 5)
    assert outcome.inventory == ()
    assert not outcome.applied and outcome.changed == 2
    assert "only 2" in outcome.note


def test_apply_change_dispatches_on_direction():
    assert apply_change([], "key", GAIN).inventory[0].name == "key"
    assert apply_change([item("key")], "key", LOSE).inventory == ()


# --- the store -------------------------------------------------------------


def test_a_tag_with_no_name_means_whoever_is_acting():
    store = InventoryStore()
    store.add(sheet("Corin Vale"))
    assert store.resolve(None, default="Corin Vale").name == "Corin Vale"


def test_a_first_name_resolves_when_it_is_unambiguous():
    store = InventoryStore()
    store.add(sheet("Corin Vale"))
    assert store.resolve("Corin").name == "Corin Vale"


def test_an_ambiguous_first_name_resolves_to_nobody():
    """With two Corins at the table, guessing who gets the sword is not the engine's
    call — and the proposal is still logged, so nothing is lost by refusing."""
    store = InventoryStore()
    store.add(sheet("Corin Vale"))
    store.add(sheet("Corin Ashe"))
    assert store.resolve("Corin") is None


def test_an_unknown_character_does_not_fall_back_to_the_acting_one():
    """The GM handing a lantern to someone who is not at the table is worth seeing in
    the log, not worth quietly giving to whoever happens to be acting."""
    store = InventoryStore()
    store.add(sheet("Corin Vale"))
    assert store.resolve("Halda Orrin", default="Corin Vale") is None


def test_applying_mutates_the_sheet_the_engine_is_holding(tmp_path):
    """One sheet object, three holders. A copy here would leave the turn engine looking
    at the inventory the party had a moment ago."""
    subject = sheet(items=[item("torch", 2)])
    store = InventoryStore()
    store.add(subject)

    store.apply(tag("torch", GAIN, 3), subject)
    assert subject.inventory[0].quantity == 5


def test_a_change_is_written_to_the_sheet_file_immediately(tmp_path):
    """Persisted per change, like the canon ledger: a session that dies at turn 40 must
    not take the party's gear with it."""
    path = tmp_path / "corin-vale.yaml"
    subject = sheet()
    subject.save(path)
    store = InventoryStore()
    store.add(subject, path=path)

    store.apply(tag("iron key"), subject)

    assert [i.name for i in CharacterSheet.load(path).inventory] == ["iron key"]


def test_a_sheet_with_no_file_still_changes_and_still_logs(tmp_path):
    """A scratch session has nowhere durable to file gear; that is not an error."""
    log = SessionLog.open(tmp_path)
    subject = sheet()
    store = InventoryStore(log=log)
    store.add(subject)

    store.apply(tag("iron key"), subject)

    assert [i.name for i in subject.inventory] == ["iron key"]
    assert any(e.type is EventType.INVENTORY_CHANGE for e in read_log(log.path))


def test_an_applied_change_is_logged_with_provenance(tmp_path):
    log = SessionLog.open(tmp_path)
    subject = sheet()
    store = InventoryStore(log=log)
    store.add(subject)

    store.apply(
        InventoryTag(item="iron key", direction=GAIN, quantity=2, raw="[[GAIN: 2 iron keys]]"),
        subject,
        turn=4,
    )

    event = next(e for e in read_log(log.path) if e.type is EventType.INVENTORY_CHANGE)
    assert (event.character, event.item, event.quantity) == ("Corin Vale", "iron key", 2)
    assert event.direction is GAIN
    assert event.confirmed is True and event.applied is True
    assert event.established_by == "[[GAIN: 2 iron keys]]"
    assert event.turn_seq == 4


def test_a_confirmed_change_the_sheet_cannot_cover_is_logged_as_unapplied(tmp_path):
    """`confirmed` is the humans agreeing; `applied` is the engine managing it. The gap
    between them is the whole measurement (D-008, amended 2026-08-13)."""
    log = SessionLog.open(tmp_path)
    subject = sheet()
    store = InventoryStore(log=log)
    store.add(subject)

    store.apply(tag("lantern", LOSE), subject)

    event = next(e for e in read_log(log.path) if e.type is EventType.INVENTORY_CHANGE)
    assert event.confirmed is True and event.applied is False


def test_a_declined_proposal_is_logged_and_the_sheet_is_untouched(tmp_path):
    log = SessionLog.open(tmp_path)
    subject = sheet(items=[item("bow")])
    store = InventoryStore(log=log)
    store.add(subject)

    store.decline(tag("bow", LOSE), character="Corin Vale")

    assert [i.name for i in subject.inventory] == ["bow"]
    event = next(e for e in read_log(log.path) if e.type is EventType.INVENTORY_CHANGE)
    assert event.confirmed is False and event.applied is False


def test_proposals_are_paired_with_the_sheets_they_meant():
    store = InventoryStore()
    store.add(sheet("Corin Vale"))
    paired = proposals_for(
        [tag("key"), tag("rope", character="Halda")], store, acting="Corin Vale"
    )
    assert paired[0][1].name == "Corin Vale"
    assert paired[1][1] is None


def test_the_line_the_table_reads_says_when_the_sheet_disagreed():
    outcome = apply_lose([], "lantern")
    assert describe_change(outcome, LOSE, "Corin") == "Corin loses lantern — not on the sheet"


# --- the turn engine collects, and performs nothing -------------------------


def _engine(responses, log=None) -> TurnEngine:
    return TurnEngine(
        backend=MockBackend(responses=responses),
        campaign=CampaignContext(
            name="The Salt Road", party=[PartyMember(name="Corin Vale", player="Kelly")]
        ),
        log=log,
    )


def test_the_engine_collects_item_tags_without_applying_them(tmp_path):
    """Items are state and confirmation is an interface act, so nothing may happen at
    the point the narration is parsed — not even a log row."""
    log = SessionLog.open(tmp_path)
    engine = _engine(["You take it. [[GAIN: iron key]]"], log=log)

    result = engine.run("I take the key", player="Kelly", sheet=sheet())

    assert [(t.item, t.direction) for t in result.inventory] == [("iron key", GAIN)]
    assert not any(e.type is EventType.INVENTORY_CHANGE for e in read_log(log.path))


def test_item_tags_never_reach_the_screen_or_the_recent_window():
    engine = _engine(["You pocket it. [[GAIN: iron key]]"])
    result = engine.run("I take the key", player="Kelly", sheet=sheet())

    assert result.narration == "You pocket it."
    assert "GAIN" not in engine.campaign.history[-1].narration


def test_a_second_call_in_the_same_turn_can_also_propose():
    """The check-then-narrate path is two GM calls, and a proposal in the second one is
    the ordinary case: the item is handed over *after* the roll."""
    engine = _engine(
        ["[[CHECK: Dexterity DC 10 — you fumble it]]", "It comes free. [[GAIN: iron key]]"]
    )
    result = engine.run("I pick the lock", player="Kelly", sheet=sheet())
    assert [t.item for t in result.inventory] == ["iron key"]


def test_the_opening_scene_can_propose_too():
    engine = _engine(["Dawn over the road. [[GAIN: travel papers]]"])
    assert [t.item for t in engine.open_scene().inventory] == ["travel papers"]


def test_a_refusal_proposes_nothing():
    refusal = GMResponse(
        text="I won't narrate that. [[GAIN: iron key]]",
        model="mock-model",
        usage=Usage(input_tokens=1, output_tokens=1),
        refused=True,
    )
    engine = _engine([refusal])
    assert engine.run("...", player="Kelly").inventory == []


# --- the confirmation prompt -----------------------------------------------


def test_confirming_applies_and_declining_does_not(monkeypatch, tmp_path):
    log = SessionLog.open(tmp_path)
    subject = sheet()
    store = InventoryStore(log=log)
    store.add(subject)
    answering(monkeypatch, "1")

    applied = confirm_inventory(
        console(), [tag("iron key"), tag("silver ring")], store, acting="Corin Vale"
    )

    assert applied == 1
    assert [i.name for i in subject.inventory] == ["iron key"]
    events = [e for e in read_log(log.path) if e.type is EventType.INVENTORY_CHANGE]
    assert [(e.item, e.confirmed) for e in events] == [
        ("iron key", True),
        ("silver ring", False),
    ]


def test_bare_enter_applies_everything(monkeypatch):
    subject = sheet()
    store = InventoryStore()
    store.add(subject)
    answering(monkeypatch, "")

    confirm_inventory(console(), [tag("key"), tag("rope")], store, acting="Corin Vale")
    assert [i.name for i in subject.inventory] == ["key", "rope"]


def test_none_applies_nothing(monkeypatch):
    subject = sheet()
    store = InventoryStore()
    store.add(subject)
    answering(monkeypatch, "none")

    assert confirm_inventory(console(), [tag("key")], store, acting="Corin Vale") == 0
    assert subject.inventory == []


def test_an_unreadable_answer_is_asked_again(monkeypatch):
    subject = sheet()
    store = InventoryStore()
    store.add(subject)
    answering(monkeypatch, "wat", "all")

    confirm_inventory(console(), [tag("key")], store, acting="Corin Vale")
    assert [i.name for i in subject.inventory] == ["key"]


def test_nobody_at_the_keyboard_declines(monkeypatch):
    """EOF is not consent. The proposal is still logged, so the evidence survives."""
    subject = sheet()
    store = InventoryStore()
    store.add(subject)

    def _eof(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("dndc.game.cli.Prompt.ask", _eof)

    assert confirm_inventory(console(), [tag("key")], store, acting="Corin Vale") == 0
    assert subject.inventory == []


def test_a_proposal_for_nobody_is_logged_without_being_offered(monkeypatch, tmp_path):
    log = SessionLog.open(tmp_path)
    store = InventoryStore(log=log)
    store.add(sheet("Corin Vale"))
    # No answer is scripted: an unresolvable proposal must not reach the prompt at all.
    answering(monkeypatch)

    applied = confirm_inventory(
        console(), [tag("lantern", character="Halda Orrin")], store, acting="Corin Vale"
    )

    assert applied == 0
    event = next(e for e in read_log(log.path) if e.type is EventType.INVENTORY_CHANGE)
    assert event.character == "Halda Orrin" and event.confirmed is False


def test_no_proposals_asks_nothing(monkeypatch):
    answering(monkeypatch)
    assert confirm_inventory(console(), [], InventoryStore(), acting="Corin Vale") == 0


# --- looking in the pack ---------------------------------------------------


def _play(text: str, store: InventoryStore | None, acting="Corin Vale") -> str:
    from dndc.game.cli import _play_command

    recorder = Console(force_terminal=False, no_color=True, record=True, width=100)
    campaign = CampaignContext(name="c", party=[PartyMember(name="Corin Vale", player="Kelly")])
    _play_command(recorder, text, campaign, builder=None, items=store, acting=acting)
    return recorder.export_text()


def test_inventory_shows_the_acting_character_by_default():
    """The GM is told it does not know what is in a pack, which only works if the
    players can look — OD-11's principle: state is displayed from state."""
    store = InventoryStore()
    store.add(sheet(items=[item("torch", 3), item("iron key")]))

    output = _play("/inventory", store)
    assert "torch ×3" in output and "iron key" in output


def test_inventory_can_name_someone_else():
    store = InventoryStore()
    store.add(sheet("Corin Vale"))
    store.add(sheet("Brother Hammond", items=[item("holy symbol")]))

    assert "holy symbol" in _play("/inventory Hammond", store)


def test_inventory_says_so_when_the_pack_is_empty():
    store = InventoryStore()
    store.add(sheet())
    assert "carrying nothing" in _play("/inventory", store)


def test_inventory_for_an_unknown_name_does_not_guess():
    store = InventoryStore()
    store.add(sheet())
    assert "no character matching" in _play("/inventory Halda", store)
