"""P4.1: NPC records, and the knowledge scope that is the structural half of D-003.

Most of this file is about what an NPC *cannot* see. That asymmetry is deliberate: the
voice card failing produces a dull innkeeper, and the knowledge scope failing produces a
villager who knows the twist — so the tests that matter are the exclusions, and they are
written as properties of the code rather than of anyone's authoring.
"""

from __future__ import annotations

import pytest

from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope, npc_issues
from dndc.gm.npcprompt import NPCPromptBuilder, NPCPromptError, NPCScene
from dndc.schema.npc import COMMON_KNOWLEDGE_TAG, NPC, NPCBook, VoiceCard, npc_id


def entry(entry_id: str, text: str, scope=CanonScope.WORLD, **fields) -> CanonEntry:
    return CanonEntry(id=entry_id, text=text, scope=scope, **fields)


@pytest.fixture
def ledger() -> CanonLedger:
    """A small campaign with one of everything an NPC must and must not see."""
    book = CanonLedger()
    for record in (
        entry("world-tide", "The spring tide floods the low road twice a month.",
              tags=(COMMON_KNOWLEDGE_TAG,)),
        entry("world-harbour-fee", "The harbourmaster takes a cut of every landing.",
              tags=("harbour",)),
        entry("world-north-road", "The north road washed out last winter.", tags=("road",)),
        entry("gm-smuggler", "The harbourmaster is the smuggling ring's paymaster.",
              scope=CanonScope.GM_ONLY, tags=("harbour",)),
        entry("player-ledger", "The party found a ledger in the customs house.",
              scope=CanonScope.PLAYER_KNOWN, tags=("harbour",)),
        entry("belief-maren", "Maren thinks the harbourmaster is merely greedy.",
              scope=CanonScope.NPC_BELIEF, subject="Maren", tags=("harbour",)),
        entry("belief-dess", "Dess thinks the tide charts have been altered.",
              scope=CanonScope.NPC_BELIEF, subject="Dess", tags=("harbour",)),
        entry("pc-wren", "Wren has forged papers since she was twelve.",
              scope=CanonScope.CHARACTER, subject="Wren"),
    ):
        book.add(record)
    return book


def maren(**fields) -> NPC:
    defaults = {
        "voice": VoiceCard(role="innkeeper at the Salt Wife", manner="dry, unhurried"),
        "knows_tags": ("harbour",),
    }
    defaults.update(fields)
    return NPC.create("Maren", **defaults)


# --- the record ------------------------------------------------------------


def test_an_npc_mints_a_readable_id():
    assert npc_id("Maren Halloway") == "maren-halloway"
    assert NPC.create("Maren").id == "maren"


def test_a_name_with_no_usable_characters_is_refused():
    with pytest.raises(ValueError):
        npc_id("!!!")


def test_the_book_round_trips_through_yaml(tmp_path):
    book = NPCBook()
    book.add(maren(location="the Salt Wife", notes="lying about the ledger"))
    path = book.save(tmp_path / "npcs.yaml")

    reloaded = NPCBook.load(path)
    assert reloaded.names() == ["Maren"]
    found = reloaded.get("MAREN")
    assert found is not None and found.voice.role == "innkeeper at the Salt Wife"
    assert found.notes == "lying about the ledger"


def test_an_absent_book_is_empty_rather_than_an_error(tmp_path):
    assert len(NPCBook.load(tmp_path / "nothing.yaml")) == 0


def test_two_npcs_cannot_share_an_id():
    """A duplicate key means one of them is voiced with the other's knowledge scope."""
    book = NPCBook()
    book.add(maren())
    with pytest.raises(ValueError, match="already in this campaign"):
        book.add(maren(knows_tags=("road",)))


def test_replace_is_the_authored_edit_path():
    book = NPCBook()
    book.add(maren())
    book.replace(maren(voice=VoiceCard(role="innkeeper", demeanour="wary of the party")))
    assert len(book) == 1
    assert book.get("maren").voice.demeanour == "wary of the party"


# --- what an NPC may see ---------------------------------------------------


def test_an_npc_sees_what_their_tags_reach(ledger):
    known = {e.id for e in ledger.for_npc(maren())}
    assert "world-harbour-fee" in known
    assert "world-north-road" not in known  # a tag she was not given


def test_common_knowledge_reaches_everyone_by_default(ledger):
    assert "world-tide" in {e.id for e in ledger.for_npc(maren())}


def test_the_stranger_who_rode_in_last_night_has_heard_none_of_it(ledger):
    outsider = maren(common_knowledge=False)
    assert "world-tide" not in {e.id for e in ledger.for_npc(outsider)}


def test_an_entry_named_outright_reaches_them_whatever_their_tags(ledger):
    """The escape hatch for "she, specifically, saw it happen"."""
    known = {e.id for e in ledger.for_npc(maren(knows_tags=(), knows=("world-north-road",)))}
    assert known == {"world-tide", "world-north-road", "belief-maren"}


def test_their_own_beliefs_reach_them(ledger):
    assert "belief-maren" in {e.id for e in ledger.for_npc(maren())}


def test_a_superseded_fact_leaves_the_prompt(ledger):
    ledger.supersede(
        "world-harbour-fee",
        entry("world-harbour-fee-2", "The harbourmaster has stopped taking a cut.",
              tags=("harbour",)),
    )
    known = {e.id for e in ledger.for_npc(maren())}
    assert "world-harbour-fee" not in known
    assert "world-harbour-fee-2" in known


# --- what an NPC can never see ---------------------------------------------


def test_gm_only_never_reaches_an_npc_even_through_a_tag(ledger):
    """The tag `harbour` reaches her; the gm_only fact carrying it does not."""
    assert "gm-smuggler" not in {e.id for e in ledger.for_npc(maren())}


def test_gm_only_never_reaches_an_npc_even_when_named_outright(ledger):
    """Unconditional, and not overridable by authoring — which is what makes "no NPC
    prompt has ever carried gm_only canon" a property of the code."""
    assert "gm-smuggler" not in {e.id for e in ledger.for_npc(maren(knows=("gm-smuggler",)))}


def test_what_the_players_know_is_not_what_this_character_has_heard(ledger):
    """The least obvious exclusion and the most load-bearing: handing over `player_known`
    would leak the party's own discoveries back into the world reacting to them.

    `player-ledger` carries the `harbour` tag Maren was granted, and is still refused —
    which is the case that matters, because the sweep writes this scope automatically and
    nobody chose that tag with an NPC in mind.
    """
    assert "player-ledger" not in {e.id for e in ledger.for_npc(maren())}


def test_player_known_is_refused_even_when_named_outright(ledger):
    assert "player-ledger" not in {e.id for e in ledger.for_npc(maren(knows=("player-ledger",)))}


def test_another_characters_beliefs_never_reach_them(ledger):
    """Even though `belief-dess` carries a tag Maren was given."""
    assert "belief-dess" not in {e.id for e in ledger.for_npc(maren())}


def test_a_belief_cannot_be_borrowed_by_naming_it(ledger):
    known = {e.id for e in ledger.for_npc(maren(knows=("belief-dess",)))}
    assert "belief-dess" not in known


def test_player_character_facts_are_not_public(ledger):
    """Co-creation backstory is `character` scope; nobody in the world was told it."""
    assert "pc-wren" not in {e.id for e in ledger.for_npc(maren())}


def test_nothing_outside_the_allow_list_gets_through(ledger):
    """The whole property in one assertion: every visible entry is visible *because* of
    something the author granted."""
    npc = maren()
    for record in ledger.for_npc(npc):
        granted = (
            record.id in npc.knows
            or set(record.tags) & set(npc.knows_tags)
            or (npc.common_knowledge and COMMON_KNOWLEDGE_TAG in record.tags)
            or (record.scope is CanonScope.NPC_BELIEF and record.subject == npc.name)
        )
        assert granted, f"{record.id} reached {npc.name} without being granted"


# --- the authoring lint ----------------------------------------------------


def test_a_knows_id_that_does_not_exist_is_reported(ledger):
    issues = npc_issues(maren(knows=("world-nonexistent",)), ledger)
    assert any("not in the ledger" in issue for issue in issues)


@pytest.mark.parametrize(
    ("entry_id", "scope"), [("gm-smuggler", "gm_only"), ("player-ledger", "player_known")]
)
def test_naming_an_unreachable_fact_is_reported_with_the_fix(ledger, entry_id, scope):
    """Silently refusing it is right; silently refusing it *without saying so* would leave
    an author believing a character knows something they do not."""
    (issue,) = [i for i in npc_issues(maren(knows=(entry_id,)), ledger) if scope in i]
    assert "npc_belief" in issue and "Maren" in issue


def test_borrowing_another_characters_belief_is_reported(ledger):
    issues = npc_issues(maren(knows=("belief-dess",)), ledger)
    assert any("Dess's belief" in issue for issue in issues)


def test_a_superseded_id_is_reported(ledger):
    ledger.supersede("world-north-road", entry("world-north-road-2", "The road reopened."))
    issues = npc_issues(maren(knows=("world-north-road",)), ledger)
    assert any("superseded" in issue for issue in issues)


def test_a_tag_no_canon_carries_is_reported(ledger):
    issues = npc_issues(maren(knows_tags=("dockside",)), ledger)
    assert any("'dockside'" in issue for issue in issues)


def test_a_character_who_knows_nothing_is_reported(ledger):
    """Nothing else in the system ever complains about this, and it is the commonest way
    an authored NPC turns out to have nothing to say."""
    silent = NPC.create("Passer-By", common_knowledge=False)
    issues = npc_issues(silent, ledger)
    assert any("knows nothing at all" in issue for issue in issues)


def test_a_well_authored_npc_has_no_issues(ledger):
    assert npc_issues(maren(knows=("world-north-road",)), ledger) == []


# --- the assembled prompt (P4.2) -------------------------------------------


def assembled(request) -> str:
    """Every byte a model would receive. What the absence tests search."""
    return "\n".join(
        [request.system, request.system_volatile, *(m.content for m in request.messages)]
    )


def built(ledger, npc=None, scene=None, **kwargs):
    return NPCPromptBuilder(**kwargs).build(
        npc or maren(), ledger, scene or NPCScene(prompt="What do you know about the harbour?")
    )


def test_the_prompt_carries_what_she_knows(ledger):
    text = assembled(built(ledger))
    assert "The harbourmaster takes a cut of every landing." in text
    assert "The spring tide floods the low road twice a month." in text


def test_the_voice_card_reaches_the_prompt(ledger):
    npc = maren(
        pronouns="she/her",
        voice=VoiceCard(
            role="innkeeper at the Salt Wife",
            persona="Forty years behind that bar.",
            manner="Dry, unhurried.",
            sample_lines=("You'll want the small room.",),
            demeanour="Civil, and unconvinced.",
        ),
    )
    text = assembled(built(ledger, npc=npc))
    for fragment in (
        "innkeeper at the Salt Wife", "she/her", "Forty years behind that bar.",
        "Dry, unhurried.", "You'll want the small room.", "Civil, and unconvinced.",
    ):
        assert fragment in text


def test_beliefs_are_marked_as_belief_rather_than_established(ledger):
    """A model that treats the two alike turns a private suspicion into common knowledge."""
    text = assembled(built(ledger))
    assert "rightly or wrongly" in text
    assert "Maren thinks the harbourmaster is merely greedy." in text


def test_the_secret_never_reaches_the_prompt(ledger):
    """The headline property of D-003, asserted on the bytes rather than on the filter.

    `gm-smuggler` carries the tag Maren was granted, so every path that could leak it is
    exercised: it is refused, and no phrasing of it appears anywhere in the call.
    """
    text = assembled(built(ledger))
    assert "smuggling" not in text
    assert "paymaster" not in text


def test_what_the_players_found_never_reaches_the_prompt(ledger):
    assert "customs house" not in assembled(built(ledger))


def test_another_characters_belief_never_reaches_the_prompt(ledger):
    assert "tide charts" not in assembled(built(ledger))


def test_the_gm_s_notes_are_never_rendered(ledger):
    """The field exists precisely for what the model voicing her must not be told, so its
    absence is a test rather than a habit."""
    npc = maren(notes="She has been paid to forget a name.")
    assert "paid to forget" not in assembled(built(ledger, npc=npc))


def test_the_prompt_forbids_nothing_by_name(ledger):
    """Substitution, never prohibition: no "do not mention" anywhere, because naming a
    secret in order to forbid it is the anti-pattern the whole design avoids."""
    text = assembled(built(ledger)).casefold()
    for phrase in ("do not mention", "don't mention", "do not reveal", "never reveal"):
        assert phrase not in text


def test_the_claims_ledger_comes_back_to_her(ledger):
    scene = NPCScene(said=["I've never met the man."], prompt="You said you knew him.")
    text = assembled(built(ledger, scene=scene))
    assert "I've never met the man." in text
    assert "Stay consistent" in text


def test_the_scene_is_the_gm_s_line_not_the_npc_s(ledger):
    request = built(ledger, scene=NPCScene(setting="The taproom, late.", prompt="Hello?"))
    assert "The taproom, late." in request.system_volatile
    assert request.messages[0].content == "Hello?"


def test_a_character_who_knows_nothing_still_has_a_prompt(ledger):
    """No canon is a quiet character, not a crash — and not a blank section either."""
    text = assembled(built(ledger, npc=NPC.create("Passer-By", common_knowledge=False)))
    assert "you have heard nothing worth repeating" in text


def test_section_order_is_data(ledger):
    npc = maren(voice=VoiceCard(role="the innkeeper", demeanour="wary"))
    forwards = built(ledger, npc=npc, order=("role", "demeanour")).system
    backwards = built(ledger, npc=npc, order=("demeanour", "role")).system
    assert forwards.index("the innkeeper") < forwards.index("wary")
    assert backwards.index("wary") < backwards.index("the innkeeper")


def test_a_section_may_be_left_out_entirely(ledger):
    """Order is the research variable; dropping a section is how you test whether it
    was ever load-bearing."""
    system = built(ledger, order=("role",)).system
    assert "dry, unhurried" not in system.casefold()


def test_an_unknown_section_is_refused(ledger):
    with pytest.raises(NPCPromptError, match="unknown prompt section"):
        NPCPromptBuilder(order=("role", "secrets"))
