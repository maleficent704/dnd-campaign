"""Drift baselines — the committed artifact the measurement runs against.

Fable, 2026-08-15: **the fixture, not the seed.** P2.6 measured survival by re-sweeping an
archived log every time, which made the baseline move — the sweep recovered 224 facts one
run and 269 the next from the same session. The obvious fix is a fixed seed, and it is the
wrong one: seed reproducibility is hostage to model version, quantization and Ollama
internals, so it breaks silently on the first upgrade. A file in git cannot move. Same
instinct as pinning the SRD.

What that buys is bigger than reproducibility. With the recovered canon in a committed
file, **the survival check needs no model, no NAS, and no log** — it is a fixture loaded
from disk and rendered through the prompt builder, so it runs offline, in the test suite,
in a second. It stops being an errand and becomes an assertion.

It also splits two things P2.6 had tangled:

* **survival** — does a known set of facts reach the prompt a session would send? Now
  deterministic, and a regression test of our own pipeline;
* **recovery stability** — re-sweep the source log and diff against the fixture. That is a
  measurement of the *model*, it is expected to vary, and it is a Phase 7 number in its own
  right rather than noise in someone else's.

A baseline says how it was made — model, temperature, date, and the hash of the log it came
from — because a measurement whose provenance is unrecorded is an anecdote. The hash is
what catches the case that matters: an archived log edited or replaced after the fixture
was cut, which would otherwise show up as the world mysteriously drifting.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field

from dndc.gm.canon import CanonEntry, CanonLedger

#: Where committed baselines live. Data, version-controlled — unlike `data/srd/normalized/`
#: which is generated and gitignored (OD-7). The whole point is that these do not move.
DEFAULT_BASELINE_ROOT = Path(__file__).resolve().parents[3] / "data" / "drift"

BASELINE_SUFFIX = ".baseline.yaml"


def digest(path: Path | str) -> str:
    """SHA-256 of a source log, so a fixture can tell if its log changed underneath it."""
    sha = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


class BaselineSource(BaseModel):
    """The session this baseline was recovered from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    log: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    session_id: str | None = None
    campaign: str | None = None
    turns: int = Field(default=0, ge=0)
    #: Facts the GM declared inline. Zero for the archived logs, which predate P2.2 —
    #: the property that makes them a before-picture, recorded so it stays visible.
    tagged: int = Field(default=0, ge=0)


class BaselineProvenance(BaseModel):
    """How the recovery was done. Not decoration: it is what makes a rerun comparable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recorded: date
    model: str | None = None
    temperature: float | None = None
    seed: int | None = None
    #: Turns per sweep call. One, in a baseline, because the origin turn of each fact is
    #: what the contradiction scan needs and the sweep will not invent it.
    chunk_turns: int = 1
    dndc_version: str | None = None
    commit_sha: str | None = None


class DriftBaseline(BaseModel):
    """A recovered world, frozen, with the receipts for how it was recovered."""

    model_config = ConfigDict(extra="forbid")

    source: BaselineSource
    provenance: BaselineProvenance
    #: Recovered canon in the order it was established. `CanonEntry.turn` carries the
    #: origin, which is what the contradiction scan reads.
    entries: list[CanonEntry] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def ledger(self) -> CanonLedger:
        """The baseline as a ledger, ready for the prompt builder."""
        return CanonLedger(entries=list(self.entries))

    def established(self) -> list[tuple[int, CanonEntry]]:
        """(origin turn, entry) pairs, the shape the contradiction scan wants."""
        return [(entry.turn or 0, entry) for entry in self.entries]

    def matches(self, log: Path | str) -> bool:
        """Is this still the log the baseline was cut from?"""
        return digest(log) == self.source.sha256

    # --- persistence -------------------------------------------------------

    @classmethod
    def load(cls, path: Path | str) -> DriftBaseline:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.model_validate(raw)

    def save(self, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_yaml(), encoding="utf-8")
        return target

    def to_yaml(self) -> str:
        payload = self.model_dump(mode="json", exclude_none=True)
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=88)


def baseline_path(log: Path | str, root: Path | None = None) -> Path:
    """Where the baseline for a given log lives. Named after the log, not the campaign —
    a campaign has many sessions and each one is its own before-picture."""
    stem = Path(log).name
    for suffix in (".jsonl", ".json"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return (root or DEFAULT_BASELINE_ROOT) / f"{stem}{BASELINE_SUFFIX}"


def load_baselines(root: Path | None = None) -> list[DriftBaseline]:
    """Every committed baseline, oldest session first. The offline survival check's input."""
    base = root or DEFAULT_BASELINE_ROOT
    if not base.is_dir():
        return []
    return [
        DriftBaseline.load(path) for path in sorted(base.glob(f"*{BASELINE_SUFFIX}"))
    ]


def record(
    entries: Sequence[tuple[int, CanonEntry]],
    source: BaselineSource,
    provenance: BaselineProvenance,
) -> DriftBaseline:
    """Freeze a recovery run into a baseline, stamping each fact with its origin turn."""
    return DriftBaseline(
        source=source,
        provenance=provenance,
        entries=[entry.model_copy(update={"turn": origin}) for origin, entry in entries],
    )
