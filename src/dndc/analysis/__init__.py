"""Instruments over the session logs — the research half of the project.

The campaign is the experiment; `logs/` is the data. This package is what reads it back.
Nothing here runs during play, nothing here writes to a campaign, and nothing here is on
a path the table can trip over — the read-only principle Fable adopted as standing
doctrine for `analysis/` (2026-08-15): an instrument that alters what it measures is not
an instrument.
"""

from dndc.analysis.cost import (
    SEAT_ORDER,
    CampaignCost,
    SeatCost,
    SessionCost,
    Summary,
    latest_log,
    logs_in,
    read_campaign,
    read_session,
)
from dndc.analysis.baseline import (
    BASELINE_SUFFIX,
    DEFAULT_BASELINE_ROOT,
    BaselineProvenance,
    BaselineSource,
    DriftBaseline,
    baseline_path,
    digest,
    load_baselines,
)
from dndc.analysis.baseline import record as record_baseline
from dndc.analysis.drift import (
    DRIFT_TEMPERATURE,
    Contradiction,
    ContradictionScan,
    DriftReport,
    StabilityReport,
    compare,
    measure,
    recover,
    store_for_replay,
    survives,
)
from dndc.analysis.replay import ReplayedSession, replay, replay_turns

__all__ = [
    "BASELINE_SUFFIX",
    "DEFAULT_BASELINE_ROOT",
    "DRIFT_TEMPERATURE",
    "BaselineProvenance",
    "BaselineSource",
    "Contradiction",
    "ContradictionScan",
    "DriftBaseline",
    "DriftReport",
    "ReplayedSession",
    "StabilityReport",
    "baseline_path",
    "compare",
    "digest",
    "load_baselines",
    "measure",
    "recover",
    "record_baseline",
    "replay",
    "replay_turns",
    "store_for_replay",
    "survives",
]
