"""P5.3: the "previously on…" — the campaign's own record, read back to the players."""

from __future__ import annotations

import pytest

from dndc.gm.chronicle import Chronicle, ChronicleEntry
from dndc.memory.recap import NO_SCENE, RecapReport, Recapper, _split
from dndc.models.base import GMBackendError
from dndc.models.mock import MockBackend
from dndc.schema.events import EventType, RecapStatus

SUMMARY = (
    "The party reached the waystation at Ashmill and spent the evening arguing with the "
    "reeve about the closed road. They left without an answer, and the reeve kept the "
    "toll he had already taken."
)


def chronicle(*summaries: str) -> Chronicle:
    return Chronicle(
        entries=[
            ChronicleEntry(id=f"s{i}", summary=text, sessions=(f"2026080{i}-000000",))
            for i, text in enumerate(summaries or (SUMMARY,), start=1)
        ]
    )


def recapper(responses, log=None, party=("Corin Vale",)) -> Recapper:
    return Recapper(backend=MockBackend(responses, repeat_last=False), log=log, party=party)


def answer(previously: str, where: str | None = None) -> str:
    tail = f"\nWHERE: {where}" if where is not None else ""
    return f"PREVIOUSLY: {previously}{tail}"


GOOD = "You argued with the reeve at Ashmill and left without an answer."


# --- the shape of a reply --------------------------------------------------


def test_the_two_halves_come_back_split():
    report = recapper([answer(GOOD, "The waystation yard, first light.")]).recap(
        "The Salt Road", chronicle()
    )

    assert report.status is RecapStatus.WRITTEN
    assert report.text == GOOD
    assert report.scene == "The waystation yard, first light."


def test_an_unlabelled_reply_is_still_worth_showing():
    """Prose the table did not need costs ten seconds; a scene guessed out of the wrong
    place starts the evening in the wrong room. So one half degrades and the other does
    not."""
    report = recapper([GOOD]).recap("The Salt Road", chronicle())

    assert report.text == GOOD
    assert report.scene is None


def test_a_refusal_to_say_where_is_taken_literally():
    report = recapper([answer(GOOD, NO_SCENE)]).recap("The Salt Road", chronicle())

    assert report.text == GOOD
    assert report.scene is None


def test_a_scene_with_no_recap_is_not_shown():
    report = recapper([f"WHERE: The yard at Ashmill."]).recap("The Salt Road", chronicle())

    assert report.shown is False


def test_split_tolerates_the_labels_a_model_actually_writes():
    assert _split("**Previously:** You left.\n**Where:** The yard.") == (
        "You left.",
        "The yard.",
    )


# --- what it may say -------------------------------------------------------


def test_a_recap_that_invents_a_name_is_retried_and_then_dropped():
    """The sweep's guard, on a third surface. A recap read aloud is believed."""
    invented = "You argued with Halda Orrin about the road."
    seat = recapper([answer(invented), answer(invented)])

    report = seat.recap("The Salt Road", chronicle())

    assert report.status is RecapStatus.UNGROUNDED
    assert "halda" in " ".join(report.invented).casefold()
    assert report.shown is False
    assert report.calls == 2


def test_the_retry_says_what_was_invented():
    seat = recapper([answer("You argued with Halda about the road."), answer(GOOD)])
    seat.recap("The Salt Road", chronicle())

    retry = seat.backend.calls[1].system
    assert "Halda" in retry
    assert "the record does not mention" in retry


def test_the_party_may_be_named_even_when_the_record_did_not():
    """A character who did nothing last session still belongs in a sentence about them."""
    report = recapper([answer("Corin Vale argued with the reeve at Ashmill.")]).recap(
        "The Salt Road", chronicle()
    )

    assert report.status is RecapStatus.WRITTEN


def test_the_record_it_reads_is_the_one_it_was_given():
    seat = recapper([answer(GOOD)])
    seat.recap("The Salt Road", chronicle(), known=["The bridge at Kell is out."])

    sent = seat.backend.calls[0].messages[0].content
    assert "Ashmill" in sent
    assert "The bridge at Kell is out." in sent


# --- failing to nothing ----------------------------------------------------


def test_a_campaign_with_no_record_is_not_asked_about():
    """A model asked to recap nothing will happily invent an evening."""
    seat = recapper([answer(GOOD)])

    report = seat.recap("The Salt Road", Chronicle())

    assert report.status is RecapStatus.SKIPPED
    assert seat.backend.calls == []


def test_a_box_that_is_asleep_costs_the_recap_and_not_the_evening():
    class Dead(MockBackend):
        def generate(self, request, on_text=None):
            raise GMBackendError("connection refused")

    report = Recapper(backend=Dead()).recap("The Salt Road", chronicle())

    assert report.status is RecapStatus.SKIPPED
    assert "connection refused" in report.error


def test_an_unexpected_failure_is_caught_too():
    class Broken(MockBackend):
        def generate(self, request, on_text=None):
            raise ValueError("something else entirely")

    report = Recapper(backend=Broken()).recap("The Salt Road", chronicle())

    assert report.status is RecapStatus.SKIPPED
    assert "ValueError" in report.error


def test_the_recapper_has_nothing_to_write_canon_with():
    """Read-only by construction, not by instruction (D-008 item 28)."""
    seat = recapper([answer(GOOD)])

    assert not hasattr(seat, "store")
    assert not hasattr(seat, "ledger")


# --- the row ---------------------------------------------------------------


def test_the_row_says_what_the_table_was_shown(tmp_path):
    from dndc.logging import SessionLog, read_log

    log = SessionLog.open(tmp_path, session_id="20260903-210000")
    seat = recapper([answer(GOOD, "The yard at Ashmill.")], log=log)
    report = seat.recap("The Salt Road", chronicle())
    report.scene_accepted = True
    seat.record(report)

    rows = [event for event in read_log(log.path) if event.type is EventType.RECAP]
    assert len(rows) == 1
    assert rows[0].text == GOOD
    assert rows[0].scene == "The yard at Ashmill."
    assert rows[0].scene_accepted is True
    assert rows[0].covers == ("20260801-000000",)
    assert rows[0].status is RecapStatus.WRITTEN


def test_a_skipped_recap_is_still_a_row(tmp_path):
    """The `unchecked` argument again: a pass that ran and produced nothing must not
    look like a pass that never ran."""
    from dndc.logging import SessionLog, read_log

    log = SessionLog.open(tmp_path, session_id="20260903-210000")
    invented = "You argued with Halda Orrin about the road."
    seat = recapper([answer(invented), answer(invented)], log=log)
    seat.record(seat.recap("The Salt Road", chronicle()))

    row = next(event for event in read_log(log.path) if event.type is EventType.RECAP)
    assert row.status is RecapStatus.UNGROUNDED
    assert row.text == ""
    assert row.invented


def test_the_call_is_costed(tmp_path):
    from dndc.logging import SessionLog, read_log

    log = SessionLog.open(tmp_path, session_id="20260903-210000")
    recapper([answer(GOOD)], log=log).recap("The Salt Road", chronicle())

    costs = [event for event in read_log(log.path) if event.type is EventType.COST]
    assert len(costs) == 1
    assert costs[0].seat == "utility_batch"


def test_a_report_with_no_log_is_not_an_error():
    seat = recapper([answer(GOOD)])

    assert seat.record(RecapReport()) is None


# --- what the players are allowed to hear ----------------------------------


def test_the_recap_is_never_handed_a_gm_only_fact():
    """The P4.1 discipline on a second surface: protection is absence, not instruction.

    A recap is read aloud. A GM-only fact reaching it would not leak into a character's
    line where the gate might catch it — it would be announced to the table.
    """
    from dndc.game.setup import _player_known
    from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope

    ledger = CanonLedger(
        entries=[
            CanonEntry(id="a", text="The road north is closed.", scope=CanonScope.PLAYER_KNOWN),
            CanonEntry(id="b", text="Corin grew up on the coast.", scope=CanonScope.CHARACTER,
                       subject="Corin Vale"),
            CanonEntry(id="c", text="The reeve was paid to close it.", scope=CanonScope.GM_ONLY),
            CanonEntry(id="d", text="A cellar runs under the waystation.", scope=CanonScope.WORLD),
        ]
    )

    known = _player_known(ledger)

    assert "The road north is closed." in known
    assert "Corin grew up on the coast." in known
    # The secret, obviously. And world canon too: the ledger is the world, not the
    # party's notes, and a fact being true does not mean anybody has found it.
    assert "The reeve was paid to close it." not in known
    assert "A cellar runs under the waystation." not in known


# --- at the table ----------------------------------------------------------


@pytest.fixture
def picked_up(tmp_path, monkeypatch):
    """A campaign with one session behind it, ready to be picked up again."""
    from dndc.game import campaign as campaign_module, cli
    from dndc.game.campaign import campaign_dir, create_campaign
    from dndc.memory.chronicle import CHRONICLE_FILENAME
    from dndc.schema.sheet import AbilityScores, CharacterSheet, HitPoints, Proficiencies

    root = tmp_path / "campaigns"
    monkeypatch.setattr(campaign_module, "default_campaigns_root", lambda: root)
    monkeypatch.setattr("dndc.game.setup.resolve_log_dir", lambda _: tmp_path / "logs")
    create_campaign("Salt Road", players=["Kelly"], scaffolding="off")
    target = campaign_dir("salt-road")
    CharacterSheet(
        name="Corin Vale",
        player="Kelly",
        species="Human",
        character_class="Rogue",
        level=2,
        abilities=AbilityScores(str=10, dex=16, con=12, int=12, wis=11, cha=14),
        proficiencies=Proficiencies(saving_throws=["dex", "int"]),
        hit_points=HitPoints(maximum=16, current=16),
        armor_class=14,
    ).save(target / "characters" / "corin-vale.yaml")
    chronicle().save(target / CHRONICLE_FILENAME)
    return target


def play(monkeypatch, gm, batch, said, extra=()):
    from dndc.game import cli

    monkeypatch.setattr("dndc.game.setup.build_gm_backend", lambda *a, **k: gm)
    monkeypatch.setattr("dndc.game.setup.build_batch_backend", lambda *a, **k: batch)
    remaining = iter(said)

    class Feed:
        @staticmethod
        def ask(*args, **kwargs):
            try:
                return next(remaining)
            except StopIteration:
                raise EOFError

    monkeypatch.setattr(cli, "Prompt", Feed)
    return cli.main([
        "play", "--campaign", "salt-road", "--no-prompt", "--no-npcs",
        "--no-sweep", "--no-chronicle", "--scaffolding", "off", *extra,
    ])


def everything(request) -> str:
    """The whole call. The scene is in `system_volatile` — D-002's split, where the
    static half is cacheable and what is true right now is not."""
    return "\n".join([
        request.system,
        request.system_volatile or "",
        *(message.content for message in request.messages),
    ])


def test_pickup_reads_the_campaign_back_and_opens_where_it_says(
    picked_up, monkeypatch, capsys
):
    gm = MockBackend(["The yard is empty at first light."])
    batch = MockBackend([answer(GOOD, "The waystation yard at Ashmill, first light.")])

    # An empty answer to the scene question is "yes"; then one turn, then the table
    # stands up.
    assert play(monkeypatch, gm, batch, ["", "I look for the reeve."]) == 0

    out = capsys.readouterr().out
    assert "Previously on Salt Road" in out
    assert GOOD in out
    # P5.4 rides on the same wiring: the evening says what it cost on the way out.
    assert "what the evening cost" in out
    # The confirmed scene is what the GM was actually handed.
    assert "The waystation yard at Ashmill" in everything(gm.calls[0])


def test_the_table_can_keep_the_scene_they_had(picked_up, monkeypatch, capsys):
    gm = MockBackend(["The road bends north."])
    batch = MockBackend([answer(GOOD, "Somewhere the party has never been.")])

    play(monkeypatch, gm, batch, ["n", "I look around."], extra=["--scene", "The ford."])

    assert "The ford." in everything(gm.calls[0])
    assert "Somewhere the party has never been" not in everything(gm.calls[0])


def test_no_recap_asks_nobody_anything(picked_up, monkeypatch, capsys):
    gm = MockBackend(["The road bends north."])
    batch = MockBackend([answer(GOOD, "The yard.")], repeat_last=False)

    assert play(monkeypatch, gm, batch, ["I look around."], extra=["--no-recap"]) == 0

    assert batch.calls == []
    assert "Previously on" not in capsys.readouterr().out
