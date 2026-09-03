"""P5.1: the save point — where the party is standing, and nothing else."""

from __future__ import annotations

import pytest

from dndc.config import load_config
from dndc.game import cli
from dndc.game.saves import Resume, SaveError, SaveStore, restore
from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.context import CampaignContext, PartyMember, SpokenLine, Turn
from dndc.logging import SessionLog, read_log
from dndc.schema.events import EventType, PlayerInput
from dndc.schema.save import SAVE_FILE, SavePoint

SCENE = "The Brakewater crossroads at dusk, beside the stalled salt caravan."


@pytest.fixture
def campaign() -> CampaignContext:
    context = CampaignContext(name="The Salt Road", scene=SCENE)
    context.party = [
        PartyMember(name="Corin Vale", player="Kelly"),
        PartyMember(name="Brother Hammond", player="Sam"),
    ]
    context.history = [
        Turn(player_input="", narration="The caravan has not moved since noon.", opening=True),
        Turn(
            player_input="I ask the guard what he saw.",
            narration="He looks at you a long moment.",
            speaker="Corin Vale",
            dialogue=(SpokenLine(speaker="the caravan guard", text="I saw her at the flap."),),
        ),
    ]
    return context


@pytest.fixture
def store(tmp_path) -> SaveStore:
    return SaveStore(tmp_path / "saves" / SAVE_FILE, "the-salt-road")


@pytest.fixture
def log(tmp_path) -> SessionLog:
    return SessionLog.open(tmp_path / "logs", session_id="20260903-201500")


# --- the file --------------------------------------------------------------


def test_a_campaign_with_no_save_is_not_an_error(store):
    assert store.load() is None


def test_record_writes_the_scene_the_turns_and_the_lineage(store, campaign, log):
    saved = store.record(campaign, acting="Corin Vale", log=log)

    assert store.path.exists()
    assert saved.scene == SCENE
    assert saved.acting == "Corin Vale"
    assert len(saved.turns) == 2
    assert saved.turns_played == 2
    assert (saved.session_id, saved.seq) == (log.session_id, log.seq)
    assert saved.log == str(log.path)
    assert saved.closed is False


def test_the_save_is_readable_yaml_a_human_could_fix(store, campaign, log):
    store.record(campaign, acting="Corin Vale", log=log)
    text = store.path.read_text(encoding="utf-8")

    assert "Brakewater" in text
    assert SavePoint.from_yaml(text).acting == "Corin Vale"


def test_the_write_leaves_no_temp_file_behind(store, campaign, log):
    store.record(campaign, log=log)

    # Atomic like a character sheet: a crash during the write of turn 40 must not take
    # the session with it, and must not leave a half-file for the next run to read.
    assert [path.name for path in store.path.parent.iterdir()] == [SAVE_FILE]


def test_for_campaign_puts_the_save_under_the_campaigns_saves_dir(tmp_path):
    store = SaveStore.for_campaign("the-salt-road", root=tmp_path)

    assert store.path == tmp_path / "the-salt-road" / "saves" / SAVE_FILE


def test_a_save_from_a_newer_version_is_refused_rather_than_half_read(store, campaign, log):
    saved = store.record(campaign, log=log)
    saved.model_copy(update={"version": saved.version + 1}).save(store.path)

    with pytest.raises(SaveError, match="newer version"):
        store.load()


def test_the_save_holds_no_canon(store, campaign, log):
    """The absence property, as with the NPC prompt: asserted on the bytes.

    `canon.yaml` owns the ledger and has its own writer. A copy in here would be a
    second authority, and two authorities for one fact drift the first time one path
    writes and the other does not.
    """
    campaign.ledger = CanonLedger(
        entries=[
            CanonEntry(
                id="secret-1",
                text="The reeve has been paid to keep the road closed.",
                scope=CanonScope.GM_ONLY,
            )
        ]
    )
    store.record(campaign, log=log)

    text = store.path.read_text(encoding="utf-8")
    assert "reeve" not in text
    assert "secret-1" not in text
    assert not hasattr(SavePoint(campaign="x"), "ledger")


# --- putting it back -------------------------------------------------------


def test_an_open_save_comes_back_whole(store, campaign, log):
    store.record(campaign, acting="Corin Vale", log=log)

    reopened = CampaignContext(name="The Salt Road")
    resume = restore(store.load(), reopened)

    assert reopened.scene == SCENE
    assert resume.turns == 2
    assert [turn.narration for turn in reopened.history] == [
        turn.narration for turn in campaign.history
    ]
    assert resume.acting == "Corin Vale"


def test_the_prompt_window_is_identical_after_a_restart(store, campaign, log):
    """The property that matters: the GM cannot tell the process restarted."""
    before = campaign.window()
    store.record(campaign, log=log)

    reopened = CampaignContext(name="The Salt Road")
    restore(store.load(), reopened)

    assert reopened.window() == before


def test_npc_dialogue_still_rides_one_turn_forward(store, campaign, log):
    """P4.5's structural protection has to survive the save, or it is not structural.

    The guard's line belongs in the *next* turn's user message and never in the
    assistant slot; a save that flattened it into the narration would teach the GM to
    write his dialogue, which is the leak the whole tier exists to stop.
    """
    campaign.record(Turn(player_input="I press him.", narration="He shifts his weight."))
    store.record(campaign, log=log)

    reopened = CampaignContext(name="The Salt Road")
    restore(store.load(), reopened)

    window = reopened.window()
    carried = [message for message in window if "I saw her at the flap." in message.content]
    assert len(carried) == 1
    assert carried[0].role.value == "user"


def test_a_closed_save_keeps_the_scene_and_drops_the_window(store, campaign, log):
    """D-002: a past session reaches the prompt as chronicle prose, not as transcript."""
    store.close(campaign, acting="Corin Vale", log=log)

    saved = store.load()
    assert saved.closed is True
    assert saved.turns == []
    assert saved.scene == SCENE
    # The count survives even though the turns do not — `resumed_turns` still has to be
    # able to say how long the last session was.
    assert saved.turns_played == 2

    reopened = CampaignContext(name="The Salt Road")
    resume = restore(saved, reopened)
    assert reopened.scene == SCENE
    assert reopened.history == []
    assert (resume.turns, resume.played) == (0, 2)


def test_a_closed_save_never_continues_the_old_session(store, campaign, log):
    store.close(campaign, log=log)

    resume = restore(store.load(), CampaignContext(name="x"))

    assert resume.continuing is False


def test_an_open_save_continues_the_session_it_came_from(store, campaign, log):
    log.emit(PlayerInput, player="Kelly", text="I ask the guard what he saw.")
    store.record(campaign, log=log)

    resume = restore(store.load(), CampaignContext(name="x"))

    assert resume.continuing is True
    assert resume.session_id == log.session_id


def test_a_save_whose_log_has_gone_keeps_the_scene_and_gives_up_the_continuity(
    store, campaign, log
):
    log.emit(PlayerInput, player="Kelly", text="hi")
    store.record(campaign, log=log)
    log.path.unlink()

    reopened = CampaignContext(name="x")
    resume = restore(store.load(), reopened)

    # Continuing `seq` into a file that is not there would restart the counter at zero
    # and claim otherwise. Losing the log costs the continuity, never the scene.
    assert resume.continuing is False
    assert resume.turns == 2
    assert reopened.scene == SCENE


def test_a_save_with_no_log_at_all_still_restores(store, campaign):
    store.record(campaign, acting="Corin Vale")

    resume = restore(store.load(), CampaignContext(name="x"))

    assert (resume.continuing, resume.turns) == (False, 2)


# --- the seat --------------------------------------------------------------


def test_the_saved_player_keeps_their_seat(campaign):
    resume = Resume(
        save=SavePoint(campaign="the-salt-road", acting="Brother Hammond"),
        turns=0,
        continuing=False,
    )

    assert cli._acting(campaign, resume) == "Brother Hammond"


def test_a_seat_named_for_somebody_no_longer_in_the_party_falls_back(campaign):
    resume = Resume(
        save=SavePoint(campaign="the-salt-road", acting="Someone Retired"),
        turns=0,
        continuing=False,
    )

    assert cli._acting(campaign, resume) == "Corin Vale"


def test_without_a_save_the_first_member_starts(campaign):
    assert cli._acting(campaign, None) == "Corin Vale"


# --- the session log -------------------------------------------------------


def test_resuming_reopens_the_same_log_and_seq_carries_on(tmp_path, monkeypatch):
    """The npc-village rider, finally doing the job it was ported for."""
    cfg = load_config()
    monkeypatch.setattr(cli, "resolve_log_dir", lambda _: tmp_path)

    first = cli.start_session_log(cfg, campaign="The Salt Road", seed=1)
    first.emit(PlayerInput, player="Kelly", text="I ask the guard what he saw.")
    stopped = first.seq

    resume = Resume(
        save=SavePoint(
            campaign="the-salt-road",
            session_id=first.session_id,
            log=str(first.path),
            turns_played=4,
        ),
        turns=4,
        continuing=True,
        log_path=first.path,
    )
    second = cli.start_session_log(cfg, campaign="The Salt Road", seed=2, resume=resume)

    assert second.path == first.path
    assert second.session_id == first.session_id
    assert second.seq == stopped + 1  # the resumed session_meta took the next number


def test_the_resumed_session_says_where_it_came_from(tmp_path, monkeypatch):
    cfg = load_config()
    monkeypatch.setattr(cli, "resolve_log_dir", lambda _: tmp_path)

    first = cli.start_session_log(cfg, campaign="The Salt Road", seed=1)
    resume = Resume(
        save=SavePoint(
            campaign="the-salt-road", session_id=first.session_id, turns_played=7
        ),
        turns=0,
        continuing=False,
    )
    second = cli.start_session_log(cfg, campaign="The Salt Road", seed=2, resume=resume)

    meta = [
        event
        for event in read_log(second.path)
        if event.type is EventType.SESSION_META
    ]
    assert len(meta) == 1
    assert meta[0].resumed_from == first.session_id
    assert meta[0].resumed_turns == 7


def test_a_fresh_session_claims_no_lineage(tmp_path, monkeypatch):
    cfg = load_config()
    monkeypatch.setattr(cli, "resolve_log_dir", lambda _: tmp_path)

    log = cli.start_session_log(cfg, campaign="The Salt Road", seed=1)

    meta = next(event for event in read_log(log.path) if event.type is EventType.SESSION_META)
    assert meta.resumed_from is None
    assert meta.resumed_turns == 0
