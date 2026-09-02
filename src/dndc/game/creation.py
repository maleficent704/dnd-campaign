"""The guided character co-creation loop (P1.4, D-005).

    player concept
      → GM interviews, one or two questions at a time
      → GM proposes a concept (never numbers)
      → engine allocates, validates, and builds the sheet
      → backstory collaboration; agreed details become canon entries
      → sheet written to campaigns/<slug>/characters/, canon to campaigns/<slug>/canon.yaml

The division of labour is D-005's: the conversation is the UX, the sheet is the output,
and the engine — not the model — decides what is legal. When a proposal *is* illegal the
engine's complaint goes back to the GM rather than to the player, and the GM tries again.
A player being told "Fighters cannot take Arcana" is the machine leaking through the one
part of this project that is supposed to feel like sitting down with a person.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Sequence

from dndc.game.campaign import CHARACTERS_DIRNAME, campaign_dir
from dndc.gm.backgroundtag import find_background, strip_background_tags
from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope
from dndc.gm.chronicle import Chronicle
from dndc.gm.creation import CreationPromptBuilder, assistant, user
from dndc.gm.proposal import ProposalError, find_facts, find_proposal, strip_tags
from dndc.logging import SessionLog
# Imported, not redefined: the constant lives with the store that owns the file during
# play (P2.1). Two constants naming the same file is exactly how a ledger ends up written
# to one path and read from another.
from dndc.memory.canon_store import CANON_FILENAME
from dndc.memory.chronicle import CHRONICLE_FILENAME
from dndc.models.base import GMBackend, GMResponse, Message, new_call_id
from dndc.models.pricing import estimate_cost
from dndc.rules.background import BackgroundError, describe_grants, validate_background
from dndc.rules.build import BuildError, build_character
from dndc.schema.campaign import (
    BACKGROUNDS_FILE,
    BackgroundBook,
    CampaignBackground,
    slugify,
)
from dndc.schema.events import (
    BackgroundWrite,
    CallStatus,
    CanonSource,
    CanonWrite,
    Cost,
    GMNarration,
    PlayerInput,
)
from dndc.schema.npc import NPCS_FILE, NPCBook
from dndc.schema.sheet import CharacterSheet
from dndc.srd.repository import SRDRepository

#: How many times the engine will hand a rejected proposal back to the GM before giving
#: up and telling the player. Two is enough for a typo or a miscounted skill list; a GM
#: that cannot produce a legal character in three tries has a prompt problem, and looping
#: on it would just spend money discovering that.
MAX_REPAIR_ATTEMPTS = 2

#: Marks creation events in the log without extending the D-008 vocabulary.
CREATION_SCENE = "character creation"

_OPENING = (
    "{player} has sat down to make a character. Greet them and open the interview."
)

#: Which player turn the engine starts insisting on a proposal. One round of questions
#: is good UX; a second is where interviews were stalling.
PROPOSE_BY_TURN = 2

_PROPOSE_NOW = (
    "[Engine: you have enough to build a character. Include a complete "
    "[[PROPOSE: ...]] block in this reply. Do not ask another question first — decide "
    "anything still open yourself, and let them correct it afterwards.]"
)


@dataclass
class CreationReply:
    """One exchange, split into what the player reads and what the engine did."""

    text: str
    sheet: CharacterSheet | None = None
    facts: list[str] = field(default_factory=list)
    #: A background the GM wrote this exchange and the table accepted. Set once, on the
    #: reply that established it — a later reply naming it again is reuse, not news.
    background: CampaignBackground | None = None
    #: Set only when the engine could not build a legal character *and* the GM could not
    #: repair it — at which point the player does need to know something is wrong.
    error: str | None = None
    responses: list[GMResponse] = field(default_factory=list)
    refused: bool = False


class CreationSession:
    """One player's interview. Holds the conversation; the builder holds none of it."""

    def __init__(
        self,
        backend: GMBackend,
        repo: SRDRepository,
        player: str,
        builder: CreationPromptBuilder | None = None,
        log: SessionLog | None = None,
        max_tokens: int = 1024,
        billing: str = "api",
        prices: dict | None = None,
        backgrounds: BackgroundBook | None = None,
        confirm_background: Callable[[CampaignBackground], bool] | None = None,
    ) -> None:
        self.backend = backend
        self.repo = repo
        self.player = player
        self.backgrounds = backgrounds if backgrounds is not None else BackgroundBook()
        self.builder = builder or CreationPromptBuilder(repo, self.backgrounds)
        self.log = log
        self.max_tokens = max_tokens
        self.billing = billing
        self.prices = prices or {}
        #: The table's say over content the GM invented (the 2026-08-15 (c) ruling). None
        #: accepts — a scripted or replayed interview has no table to ask, and the CLI
        #: always passes one.
        self.confirm_background = confirm_background

        self.messages: list[Message] = []
        self.sheet: CharacterSheet | None = None
        self.facts: list[str] = []
        #: Backgrounds confirmed this interview — what `finish` has to write.
        self.new_backgrounds: list[CampaignBackground] = []
        #: Player turns so far — what the propose-now nudge is timed off.
        self.turns = 0

    # --- the loop ----------------------------------------------------------

    def open(self, on_text: Callable[[str], None] | None = None) -> CreationReply:
        """The GM's opening question."""
        return self._exchange(user(_OPENING.format(player=self.player)), on_text)

    def say(
        self, text: str, on_text: Callable[[str], None] | None = None
    ) -> CreationReply:
        self._emit(PlayerInput, player=self.player, text=text)
        self.turns += 1

        content = text
        if self.sheet is None and self.turns >= PROPOSE_BY_TURN:
            # The prompt already says to propose by now, and three live interviews in a
            # row ignored it and asked another round of questions instead. Same lesson as
            # OD-12: a rule the model has to remember eventually fails, a rule carried by
            # what enters the prompt does not. So the engine says it, every turn, until
            # there is a character.
            content = f"{text}\n\n{_PROPOSE_NOW}"
        return self._exchange(user(content), on_text)

    def _exchange(
        self,
        message: Message,
        on_text: Callable[[str], None] | None,
        attempt: int = 0,
    ) -> CreationReply:
        self.messages.append(message)
        response = self._call(on_text)
        self.messages.append(assistant(response.text))

        reply = CreationReply(
            text=strip_tags(strip_background_tags(response.text)), responses=[response]
        )
        if response.refused:
            reply.refused = True
            return reply

        reply.facts = self._record_facts(response.text)

        # Before the proposal, because the proposal names it: a background declared in
        # this reply has to be in the book by the time `build_character` resolves it.
        try:
            reply.background = self._record_background(response.text)
        except BackgroundError as exc:
            return self._repair(str(exc), on_text, attempt, reply)

        try:
            proposal = find_proposal(response.text, player=self.player)
        except ProposalError as exc:
            return self._repair(str(exc), on_text, attempt, reply)

        if proposal is None:
            return reply

        # Caught live: handed a player called Kelly, the GM proposed a character called
        # Kelly. It never asked for a name and defaulted to the one in front of it. The
        # prompt now asks for a real name; this is the guard that makes it stick.
        if proposal.concept.name.strip().casefold() == self.player.strip().casefold():
            return self._repair(
                f"the character is named after the player ({self.player}). Characters "
                "need their own name — ask what they are called, or offer two or three "
                "that suit them.",
                on_text,
                attempt,
                reply,
            )

        try:
            self.sheet = build_character(proposal.concept, self.repo, self.backgrounds.get)
        except BuildError as exc:
            return self._repair(str(exc), on_text, attempt, reply)

        reply.sheet = self.sheet
        return reply

    def _repair(
        self,
        problem: str,
        on_text: Callable[[str], None] | None,
        attempt: int,
        reply: CreationReply,
    ) -> CreationReply:
        """Hand the engine's objection back to the GM, not to the player."""
        if attempt >= MAX_REPAIR_ATTEMPTS:
            reply.error = problem
            return reply

        follow_up = self._exchange(
            user(
                f"The engine rejected that proposal: {problem}\n\n"
                "Fix it and send the corrected [[PROPOSE: ...]] block. Do not mention "
                "this exchange to the player — carry on as though nothing happened."
            ),
            on_text,
            attempt=attempt + 1,
        )
        # The failed reply's prose was already shown; only the correction is new.
        follow_up.facts = reply.facts + follow_up.facts
        follow_up.responses = reply.responses + follow_up.responses
        # A background confirmed before the rejected proposal survives the repair — the
        # table already said yes to it, and the objection was about the character.
        follow_up.background = follow_up.background or reply.background
        return follow_up

    def _record_facts(self, text: str) -> list[str]:
        """New facts from this reply, in order, ignoring ones already recorded."""
        fresh = [fact for fact in find_facts(text) if fact not in self.facts]
        self.facts.extend(fresh)
        return fresh

    def _record_background(self, text: str) -> CampaignBackground | None:
        """Validate, confirm and file a background the GM wrote (the 2026-08-15 (c) ruling).

        Raises `BackgroundError` both when the engine will not grant it and when the table
        says no. The two travel the same route deliberately: either way the answer is "not
        that one, write another", it goes to the GM rather than the player (D-005), and the
        GM has one reply in which to fix it.

        Every proposal is logged, refusals included. What a model invented and the humans
        declined measures the model, and only exists as a measurement if it is written down.
        """
        tag = find_background(text)
        if tag is None:
            return None

        background = validate_background(
            name=tag.name,
            skills=tag.skills,
            tool=tag.tool,
            language=tag.language,
            feature=tag.feature,
            description=tag.description,
            srd_names=[entry.name for entry in self.repo.data.backgrounds.values()],
            existing={entry.name: entry for entry in self.backgrounds},
            languages_known=self.repo.known_languages(),
        )

        if self.backgrounds.get(background.name) is not None:
            # The campaign already has it, unchanged — the GM naming what it already
            # carries. Reuse, so there is nothing to confirm and nothing to write.
            return None

        confirmed = (
            self.confirm_background(background) if self.confirm_background else True
        )
        self._emit(
            BackgroundWrite,
            name=background.name,
            skills=[skill.value for skill in background.skills],
            tools=list(background.tools),
            languages=list(background.languages),
            feature=background.feature,
            character=self.sheet.name if self.sheet is not None else None,
            established_by=tag.raw,
            confirmed=confirmed,
            applied=confirmed,
        )
        if not confirmed:
            raise BackgroundError(
                "the table declined that background. Write a different one — a different "
                "name and a different pair of skills — or use one that already exists."
            )

        filed = background.model_copy(update={"established": date.today()})
        self.backgrounds.add(filed)
        self.new_backgrounds.append(filed)
        return filed

    # --- the call ----------------------------------------------------------

    def _call(self, on_text: Callable[[str], None] | None) -> GMResponse:
        # Minted here so the pending row can carry it — see turn.py on OD-9.
        call_id = new_call_id()
        request = self.builder.build(
            self.messages,
            sheet=self.sheet,
            facts=self.facts,
            max_tokens=self.max_tokens,
            call_id=call_id,
        )
        self._emit(
            GMNarration, text="", status=CallStatus.PENDING, call_id=call_id,
            scene=CREATION_SCENE,
        )
        try:
            response = self.backend.generate(request, on_text=on_text)
        except Exception:
            self._emit(
                GMNarration, text="", status=CallStatus.FAILED, call_id=call_id,
                scene=CREATION_SCENE,
            )
            raise

        self._emit(
            GMNarration,
            text=response.text,
            model=response.model,
            status=CallStatus.COMPLETE,
            call_id=response.call_id,
            scene=CREATION_SCENE,
        )
        self._emit_cost(response)
        return response

    # --- finishing ---------------------------------------------------------

    def finish(
        self, campaign_slug: str, root: Path | None = None
    ) -> tuple[Path, Path, Path | None]:
        """Write the sheet, the backstory canon, and any background this interview wrote.

        The third path is `None` when the character took one that already existed — most
        characters after the first few, once the campaign has a shelf of them.
        """
        if self.sheet is None:
            raise BuildError("no character has been built yet")

        target = campaign_dir(campaign_slug, root)
        if not target.exists():
            raise BuildError(f"no campaign at {target}")

        characters = target / CHARACTERS_DIRNAME
        characters.mkdir(parents=True, exist_ok=True)
        sheet_path = characters / f"{slugify(self.sheet.name)}.yaml"
        self.sheet.save(sheet_path)

        backgrounds_path = self._save_backgrounds(target)

        canon_path = target / CANON_FILENAME
        ledger = CanonLedger.load(canon_path)
        for entry in self._canon_entries(ledger):
            ledger.add(entry)
            self._emit(
                CanonWrite,
                entry_id=entry.id,
                scope=entry.scope.value,
                statement=entry.text,
                established_by=f"co-creation ({self.player})",
                source=CanonSource.CO_CREATION,
            )
        ledger.save(canon_path)
        return sheet_path, canon_path, backgrounds_path

    def _save_backgrounds(self, target: Path) -> Path | None:
        """File this interview's backgrounds, stamped with who they were written for.

        Provenance is stamped here rather than at confirmation because that is the first
        moment the character has a settled name — the background is proposed before the
        sheet exists, and often before anyone has decided what she is called.
        """
        if not self.new_backgrounds:
            return None
        assert self.sheet is not None

        written = {background.name for background in self.new_backgrounds}
        for index, held in enumerate(self.backgrounds.backgrounds):
            if held.name in written and held.proposed_for is None:
                self.backgrounds.backgrounds[index] = held.model_copy(
                    update={"proposed_for": self.sheet.name}
                )
        return self.backgrounds.save(target / BACKGROUNDS_FILE)

    def _canon_entries(self, ledger: CanonLedger) -> list[CanonEntry]:
        """Backstory facts as `character`-scope canon, with ids that do not collide."""
        assert self.sheet is not None
        stem = f"pc-{slugify(self.sheet.name)}"
        taken = {entry.id for entry in ledger}
        entries = []
        for fact in self.facts:
            index = len(entries) + 1
            entry_id = f"{stem}-{index}"
            while entry_id in taken:
                index += 1
                entry_id = f"{stem}-{index}"
            taken.add(entry_id)
            entries.append(
                CanonEntry(
                    id=entry_id,
                    text=fact,
                    scope=CanonScope.CHARACTER,
                    subject=self.sheet.name,
                )
            )
        return entries

    # --- logging -----------------------------------------------------------

    def _emit(self, event_type, **fields) -> int | None:
        if self.log is None:
            return None
        return self.log.emit(event_type, **fields).seq

    def _emit_cost(self, response: GMResponse) -> None:
        if self.log is None:
            return
        usage = response.usage
        estimated = estimate_cost(usage, response.model, self.prices) if self.prices else None
        self.log.emit(
            Cost,
            seat="gm",
            model=response.model,
            billing=self.billing,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            usd=response.reported_usd if response.reported_usd is not None else estimated,
            would_have_cost=self.billing == "subscription",
            call_id=response.call_id,
        )


def load_campaign_sheets(campaign_slug: str, root: Path | None = None) -> list[CharacterSheet]:
    """Every saved character in a campaign, name-ordered.

    This is what lets `dndc play --campaign` start without `--character` flags — the
    sheets co-creation wrote are simply there.
    """
    characters = campaign_dir(campaign_slug, root) / CHARACTERS_DIRNAME
    if not characters.is_dir():
        return []
    return sorted(
        (CharacterSheet.load(path) for path in characters.glob("*.yaml")),
        key=lambda sheet: sheet.name,
    )


def load_campaign_canon(campaign_slug: str, root: Path | None = None) -> CanonLedger:
    return CanonLedger.load(campaign_dir(campaign_slug, root) / CANON_FILENAME)


def load_campaign_backgrounds(
    campaign_slug: str, root: Path | None = None
) -> BackgroundBook:
    """The campaign's own backgrounds. An absent file is an empty book, not an error."""
    return BackgroundBook.load(campaign_dir(campaign_slug, root) / BACKGROUNDS_FILE)


def load_campaign_npcs(campaign_slug: str, root: Path | None = None) -> NPCBook:
    """The campaign's cast (P4.1). An absent file is an empty book, not an error."""
    return NPCBook.load(campaign_dir(campaign_slug, root) / NPCS_FILE)


def load_campaign_chronicle(campaign_slug: str, root: Path | None = None) -> Chronicle:
    return Chronicle.load(campaign_dir(campaign_slug, root) / CHRONICLE_FILENAME)


def summarize(sheet: CharacterSheet, facts: Sequence[str] = ()) -> str:
    """A one-line description for confirmation prompts and logs."""
    line = f"{sheet.name} — level {sheet.level} {sheet.species} {sheet.character_class}"
    if sheet.background:
        line += f" ({sheet.background})"
    if facts:
        line += f", {len(facts)} backstory fact(s)"
    return line
