"""P1.4: the guided co-creation loop (D-005).

Offline throughout — the GM is a `MockBackend` replaying scripted replies, which is what
lets the interesting cases (an illegal proposal, a silent repair) be tested at all.
"""

from __future__ import annotations

import pytest

from dndc.game import campaign as campaign_module
from dndc.game.campaign import create_campaign
from dndc.game.creation import (
    CANON_FILENAME,
    MAX_REPAIR_ATTEMPTS,
    CreationSession,
    load_campaign_canon,
    load_campaign_sheets,
    summarize,
)
from dndc.gm.canon import CanonScope
from dndc.gm.creation import CreationPromptBuilder, render_options
from dndc.logging import SessionLog, read_log
from dndc.models.mock import MockBackend
from dndc.schema.events import EventType
from dndc.schema.sheet import Ability
from dndc.srd.repository import SRDRepository

PROPOSAL = """That sounds like a soldier who never quite left the war.

[[PROPOSE:
name: Brannoc Thorn
species: Human
class: Fighter
background: Soldier
priority: str, con, dex, wis, cha, int
skills: athletics, intimidation
languages: dwarvish
armor: chain mail
shield: yes
]]"""

ILLEGAL = PROPOSAL.replace("skills: athletics, intimidation", "skills: arcana, athletics")


@pytest.fixture(scope="module")
def repo() -> SRDRepository:
    return SRDRepository.load()


@pytest.fixture
def campaigns_root(tmp_path, monkeypatch):
    root = tmp_path / "campaigns"
    monkeypatch.setattr(campaign_module, "default_campaigns_root", lambda: root)
    return root


def session(repo, responses, log=None) -> CreationSession:
    return CreationSession(
        backend=MockBackend(responses=responses),
        repo=repo,
        player="Kelly",
        log=log,
    )


# --- the interview ---------------------------------------------------------


def test_the_opening_asks_rather_than_proposes(repo):
    convo = session(repo, ["What kind of person do you want to play?"])
    reply = convo.open()
    assert reply.sheet is None
    assert "What kind of person" in reply.text


def test_a_proposal_becomes_a_validated_sheet(repo):
    convo = session(repo, ["ignored opener", PROPOSAL])
    convo.open()
    reply = convo.say("A soldier, I think.")

    assert reply.sheet is not None
    assert reply.sheet.name == "Brannoc Thorn"
    assert reply.sheet.armor_class == 18
    assert convo.sheet is reply.sheet


def test_the_player_never_sees_the_tag(repo):
    convo = session(repo, [PROPOSAL])
    reply = convo.open()
    assert "PROPOSE" not in reply.text
    assert "That sounds like a soldier" in reply.text


def test_facts_are_collected_across_the_conversation(repo):
    convo = session(
        repo,
        [
            "[[FACT: Brannoc served at Kelmore.]]",
            "[[FACT: His brother died there.]] [[FACT: Brannoc served at Kelmore.]]",
        ],
    )
    convo.open()
    reply = convo.say("Yes, and his brother?")

    # The repeated fact is not recorded twice.
    assert reply.facts == ["His brother died there."]
    assert convo.facts == ["Brannoc served at Kelmore.", "His brother died there."]


def test_the_conversation_accumulates(repo):
    """Creation is a bounded interview, so unlike play it keeps its own history."""
    convo = session(repo, ["one", "two", "three"])
    convo.open()
    convo.say("hello")
    assert [message.content for message in convo.messages][-3:] == ["one", "hello", "two"]


# --- repair ----------------------------------------------------------------


def test_an_illegal_proposal_is_repaired_without_the_player_seeing_it(repo):
    convo = session(repo, [ILLEGAL, PROPOSAL])
    reply = convo.open()

    assert reply.error is None
    assert reply.sheet is not None
    assert reply.sheet.name == "Brannoc Thorn"


def test_the_engines_complaint_is_what_goes_back_to_the_gm(repo):
    backend = MockBackend(responses=[ILLEGAL, PROPOSAL])
    convo = CreationSession(backend=backend, repo=repo, player="Kelly")
    convo.open()

    repair = [m.content for m in convo.messages if "engine rejected" in m.content]
    assert len(repair) == 1
    assert "cannot take arcana" in repair[0]


def test_a_gm_that_cannot_produce_a_legal_character_gives_up(repo):
    convo = session(repo, [ILLEGAL] * (MAX_REPAIR_ATTEMPTS + 2))
    reply = convo.open()

    assert reply.sheet is None
    assert reply.error is not None and "arcana" in reply.error


def test_a_character_named_after_the_player_is_rejected(repo):
    """Caught live: asked to build for Kelly, the GM proposed a character called Kelly."""
    named_after = PROPOSAL.replace("name: Brannoc Thorn", "name: Kelly")
    convo = session(repo, [named_after, PROPOSAL])
    reply = convo.open()

    assert reply.sheet is not None and reply.sheet.name == "Brannoc Thorn"
    complaint = [m.content for m in convo.messages if "named after the player" in m.content]
    assert len(complaint) == 1


def test_the_name_guard_ignores_case_and_padding(repo):
    convo = session(repo, [PROPOSAL.replace("name: Brannoc Thorn", "name:  kelly ")] * 4)
    reply = convo.open()
    assert reply.sheet is None and "named after the player" in (reply.error or "")


def test_a_malformed_proposal_is_repaired_the_same_way(repo):
    broken = "[[PROPOSE:\nname: X\nspecies: Human\nclass: Fighter\npriority: str, con\n]]"
    convo = session(repo, [broken, PROPOSAL])
    reply = convo.open()
    assert reply.sheet is not None


# --- finishing -------------------------------------------------------------


def test_finish_writes_the_sheet_and_the_canon(repo, campaigns_root):
    create_campaign("The Hollow Road", players=["Kelly"])
    convo = session(repo, [PROPOSAL, "[[FACT: Brannoc owes the Kelmore garrison a debt.]]"])
    convo.open()
    convo.say("Tell me about his debts.")

    sheet_path, canon_path = convo.finish("the-hollow-road")

    assert sheet_path.name == "brannoc-thorn.yaml"
    assert sheet_path.parent == campaigns_root / "the-hollow-road" / "characters"
    assert canon_path.name == CANON_FILENAME

    (loaded,) = load_campaign_sheets("the-hollow-road")
    assert loaded.name == "Brannoc Thorn"
    assert loaded.abilities.score(Ability.STR) == 16


def test_backstory_facts_land_as_character_scope_canon(repo, campaigns_root):
    create_campaign("The Hollow Road")
    convo = session(repo, [PROPOSAL, "[[FACT: Brannoc owes a debt.]]"])
    convo.open()
    convo.say("debts?")
    convo.finish("the-hollow-road")

    ledger = load_campaign_canon("the-hollow-road")
    (entry,) = list(ledger)
    assert entry.scope is CanonScope.CHARACTER
    assert entry.subject == "Brannoc Thorn"
    assert entry.text == "Brannoc owes a debt."
    assert entry.id == "pc-brannoc-thorn-1"


def test_a_second_character_does_not_collide_with_the_first(repo, campaigns_root):
    create_campaign("The Hollow Road")
    for _ in range(2):
        convo = session(repo, [PROPOSAL, "[[FACT: Brannoc owes a debt.]]"])
        convo.open()
        convo.say("debts?")
        convo.finish("the-hollow-road")

    ledger = load_campaign_canon("the-hollow-road")
    assert [entry.id for entry in ledger] == ["pc-brannoc-thorn-1", "pc-brannoc-thorn-2"]


def test_finishing_without_a_character_is_an_error(repo, campaigns_root):
    create_campaign("The Hollow Road")
    convo = session(repo, ["still talking"])
    convo.open()
    with pytest.raises(Exception, match="no character has been built"):
        convo.finish("the-hollow-road")


def test_finishing_into_a_campaign_that_does_not_exist_is_an_error(repo, campaigns_root):
    convo = session(repo, [PROPOSAL])
    convo.open()
    with pytest.raises(Exception, match="no campaign at"):
        convo.finish("nowhere")


def test_loading_sheets_from_an_empty_campaign(repo, campaigns_root):
    create_campaign("Empty")
    assert load_campaign_sheets("empty") == []
    assert len(load_campaign_canon("empty")) == 0


# --- logging ---------------------------------------------------------------


def test_the_call_is_logged_pending_then_complete_with_one_call_id(repo, tmp_path):
    log = SessionLog.open(tmp_path)
    convo = session(repo, [PROPOSAL], log=log)
    convo.open()

    events = read_log(log.path)
    narrations = [e for e in events if e.type is EventType.GM_NARRATION]
    assert [e.status.value for e in narrations] == ["pending", "complete"]
    assert narrations[0].call_id == narrations[1].call_id
    # Marked as creation without extending the D-008 vocabulary.
    assert all(e.scene == "character creation" for e in narrations)

    (cost,) = [e for e in events if e.type is EventType.COST]
    assert cost.call_id == narrations[1].call_id


def test_canon_writes_are_logged_with_provenance(repo, campaigns_root, tmp_path):
    create_campaign("The Hollow Road")
    log = SessionLog.open(tmp_path)
    convo = session(repo, [PROPOSAL, "[[FACT: Brannoc owes a debt.]]"], log=log)
    convo.open()
    convo.say("debts?")
    convo.finish("the-hollow-road")

    (write,) = [e for e in read_log(log.path) if e.type is EventType.CANON_WRITE]
    assert write.entry_id == "pc-brannoc-thorn-1"
    assert write.scope == "character"
    assert write.established_by == "co-creation (Kelly)"


def test_a_failed_call_writes_a_terminal_row(repo, tmp_path):
    class Exploding(MockBackend):
        def generate(self, request, on_text=None):
            raise RuntimeError("connection reset")

    log = SessionLog.open(tmp_path)
    convo = CreationSession(backend=Exploding(), repo=repo, player="Kelly", log=log)
    with pytest.raises(RuntimeError):
        convo.open()

    statuses = [e.status.value for e in read_log(log.path) if e.type is EventType.GM_NARRATION]
    assert statuses == ["pending", "failed"]


# --- the prompt ------------------------------------------------------------


def test_the_srd_menu_lists_only_what_exists(repo):
    options = render_options(repo)
    assert "Dragonborn" in options and "Aarakocra" not in options
    assert "**Fighter**" in options
    assert "choose 4 from" in options  # the rogue
    assert "*(spellcaster)*" in options


def test_the_system_prompt_carries_the_menu_and_the_tag_format(repo):
    builder = CreationPromptBuilder(repo)
    system = builder.system()
    assert "[[PROPOSE:" in system and "[[FACT:" in system
    assert "Halfling" in system


def test_the_draft_state_is_volatile_and_the_menu_is_not(repo):
    """Cache discipline: the sheet changes mid-interview, the rules do not."""
    builder = CreationPromptBuilder(repo)
    convo = session(repo, [PROPOSAL])
    convo.open()

    empty = builder.build(convo.messages)
    drafted = builder.build(convo.messages, sheet=convo.sheet, facts=["a fact"])

    assert "Brannoc Thorn" in drafted.system_volatile
    assert "a fact" in drafted.system_volatile
    # The cached half must not move when the draft does — that is the whole property.
    assert drafted.system == empty.system
    assert empty.system_volatile == ""
    assert drafted.cache_system


def test_the_draft_state_is_empty_before_anything_is_built(repo):
    assert CreationPromptBuilder(repo).draft_state(None, []) == ""


def test_summarize_reads_as_a_sentence(repo):
    convo = session(repo, [PROPOSAL])
    convo.open()
    assert summarize(convo.sheet, ["a fact"]) == (
        "Brannoc Thorn — level 1 Human Fighter (Soldier), 1 backstory fact(s)"
    )


# --- convergence (three live interviews stalled before this) ----------------


def test_the_engine_insists_on_a_proposal_after_the_first_round(repo):
    convo = session(repo, ["questions", "more questions", "still more"])
    convo.open()
    convo.say("a con artist")
    convo.say("yes, that one")

    nudged = [m.content for m in convo.messages if "Engine:" in m.content]
    assert len(nudged) == 1
    assert "[[PROPOSE:" in nudged[0]
    assert nudged[0].startswith("yes, that one")


def test_the_first_player_turn_is_left_alone(repo):
    """One round of questions is good UX; the nudge is for the round after."""
    convo = session(repo, ["questions", "more"])
    convo.open()
    convo.say("a con artist")
    assert not any("Engine:" in m.content for m in convo.messages)


def test_the_nudge_stops_once_a_character_exists(repo):
    convo = session(repo, ["opener", PROPOSAL, "and now backstory"])
    convo.open()
    convo.say("a soldier")       # builds the sheet
    convo.say("tell me more")    # turn 2, but there is already a character
    assert not any("Engine:" in m.content for m in convo.messages)
