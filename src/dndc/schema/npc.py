"""NPC records — the voice card and the knowledge scope (P4.1, D-003).

An NPC in this engine is two things kept deliberately apart:

- a **voice card**: who they are and how they talk. Flavour, and the whole of what makes
  a local 70B sound like an innkeeper rather than an assistant.
- a **knowledge scope**: what canon this character may be told about. Not flavour. This is
  the structural half of D-003, and it is the reason the ledger has scopes at all.

**Substitution, never prohibition.** The scope is a list of what an NPC *knows*, never a
list of what they must not say. The prompt is assembled from the first and can never
contain the second, so a secret is protected by being absent from the call rather than by
an instruction the model has to keep remembering — the pink-elephant anti-pattern the
mystery's tiered architecture was built to avoid.

**What an NPC never sees, by construction:**

- `gm_only` canon. The twist, the villain, the trap. There is no field here that could
  admit one, and `CanonLedger.for_npc` refuses the scope outright.
- another NPC's beliefs. `npc_belief` entries belong to their `subject` and nobody else;
  a village where everyone knows what everyone else privately thinks is a village with no
  secrets in it.
- **`player_known` canon.** The least obvious and the most load-bearing: what the
  *players* have established is not what this character has heard. Unconditional rather
  than merely default, because the end-of-session sweep writes this scope automatically
  (P2.3 forces it in code) — so it is the one bucket that fills with everything the party
  did and learned without anyone authoring it, and a leak there would grow by itself.

So an NPC sees what they were given: entries tagged with something in `knows_tags`,
entries named outright in `knows`, whatever is common knowledge in this campaign, and
their own beliefs. Nothing else reaches the call.

Hand-authorable throughout: `npcs.yaml` sits beside `canon.yaml`, is read by humans, and
is the file a GM edits when a character turns out to know something they did not.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field

#: Canon every NPC in the campaign may be told — the weather, the war, who runs the town.
#: A tag rather than a scope, because "what everyone knows" is a property of the fact and
#: not of the teller, and the ledger already carries tags.
COMMON_KNOWLEDGE_TAG = "common"

#: `npcs.yaml`, beside `canon.yaml` and `backgrounds.yaml` — campaign data, not ruleset.
NPCS_FILE = "npcs.yaml"


def npc_id(name: str) -> str:
    """A stable, readable key. Names are what the GM writes; ids are what files key on."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().casefold()).strip("-")
    if not slug:
        raise ValueError(f"NPC name {name!r} has no usable characters")
    return slug


class VoiceCard(BaseModel):
    """How this character sounds. Pure flavour, and pure load-bearing flavour.

    Separate from the knowledge scope because the two fail differently: a thin voice card
    makes a dull NPC, and a wrong knowledge scope leaks the plot. Keeping them apart means
    a session can rewrite the first freely without touching the second.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: One line: "the innkeeper at the Salt Wife, forty years behind that bar".
    role: str = ""
    #: Free text: age, bearing, what they want, what they are afraid of.
    persona: str = ""
    #: How they talk — rhythm, register, habits of speech. The 70B leans hard on this.
    manner: str = ""
    #: A handful of lines in their voice. Worth more than any amount of description,
    #: because a model imitates an example and paraphrases a description.
    sample_lines: tuple[str, ...] = ()
    #: How they are with the party *right now*. The one voice-card field that moves in
    #: play, which is why it is here and not in the persona.
    demeanour: str = ""


class NPC(BaseModel):
    """One NPC the engine will voice: identity, voice card, and knowledge scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    #: Free text, and used verbatim in the prompt. Absent means the prompt says nothing
    #: about it rather than guessing — a guess here is a character described wrongly to
    #: the model voicing them.
    pronouns: str = ""
    voice: VoiceCard = VoiceCard()
    #: Canon tags this character has access to. The main authoring dial: tag a fact
    #: `harbour` and every NPC who works the harbour knows it.
    knows_tags: tuple[str, ...] = ()
    #: Canon entry ids this character knows outright, whatever their tags say. The escape
    #: hatch for "she, specifically, saw it happen".
    knows: tuple[str, ...] = ()
    #: Whether campaign common knowledge reaches them. True for almost everyone; False is
    #: for the stranger who rode in last night and has heard none of it.
    common_knowledge: bool = True
    #: Where they are. Not enforced by anything yet — it is what a GM greps for.
    location: str = ""
    #: Author's notes. **Never assembled into a prompt** — this is the field for "she is
    #: lying about the ledger", which is exactly the kind of thing that must not reach the
    #: model voicing her.
    notes: str = ""

    @classmethod
    def create(cls, name: str, **fields) -> Self:
        """Build one from a name, minting the id. What the GM's own tools will call."""
        return cls(id=npc_id(name), name=name.strip(), **fields)


class NPCBook(BaseModel):
    """`campaigns/<slug>/npcs.yaml` — every NPC this campaign can voice.

    Beside the canon ledger and for the same reason: a cast that does not survive the
    process is a cast that gets reinvented, and an NPC reinvented is an NPC whose
    knowledge scope quietly changed.
    """

    model_config = ConfigDict(extra="forbid")

    npcs: list[NPC] = Field(default_factory=list)

    def __iter__(self) -> Iterator[NPC]:  # type: ignore[override]
        return iter(self.npcs)

    def __len__(self) -> int:
        return len(self.npcs)

    def names(self) -> list[str]:
        return [npc.name for npc in self.npcs]

    def get(self, key: str) -> NPC | None:
        """By id or by name, case-insensitively — the GM writes names, files hold ids."""
        if not key:
            return None
        folded = key.strip().casefold()
        for npc in self.npcs:
            if npc.id == folded or npc.name.casefold() == folded:
                return npc
        return None

    def add(self, npc: NPC) -> NPC:
        """Add one. A duplicate id is a bug, not something to silently overwrite —
        `CanonLedger.add`'s posture, and for the same reason: two characters sharing a key
        means one of them is being voiced with the other's knowledge scope."""
        if self.get(npc.id) is not None:
            raise ValueError(f"an NPC with id {npc.id!r} is already in this campaign")
        self.npcs.append(npc)
        return npc

    def replace(self, npc: NPC) -> NPC:
        """Overwrite by id — the authored-edit path, and how a demeanour changes."""
        for index, held in enumerate(self.npcs):
            if held.id == npc.id:
                self.npcs[index] = npc
                return npc
        return self.add(npc)

    def to_yaml(self) -> str:
        payload = self.model_dump(mode="json", exclude_defaults=True)
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    @classmethod
    def load(cls, path: Path | str) -> Self:
        target = Path(path)
        if not target.exists():
            return cls()
        return cls.model_validate(yaml.safe_load(target.read_text(encoding="utf-8")) or {})

    def save(self, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_yaml(), encoding="utf-8")
        return target
