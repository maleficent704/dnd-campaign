"""Instruments over the session logs — the research half of the project.

The campaign is the experiment; `logs/` is the data. This package is what reads it back.
Nothing here runs during play, nothing here writes to a campaign, and nothing here is on
a path the table can trip over.
"""

from dndc.analysis.drift import (
    DRIFT_TEMPERATURE,
    Contradiction,
    ContradictionScan,
    DriftReport,
    measure,
    recover,
    store_for_replay,
    survives,
)
from dndc.analysis.replay import ReplayedSession, replay, replay_turns

__all__ = [
    "DRIFT_TEMPERATURE",
    "Contradiction",
    "ContradictionScan",
    "DriftReport",
    "ReplayedSession",
    "measure",
    "recover",
    "replay",
    "replay_turns",
    "store_for_replay",
    "survives",
]
