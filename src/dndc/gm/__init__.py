"""GM brain: prompt assembly, canon ledger, NPC gating, threshold escalation."""

from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope, render_entries
from dndc.gm.context import (
    DEFAULT_WINDOW,
    SCAFFOLDING_TEMPLATES,
    CampaignContext,
    GMPromptBuilder,
    PartyMember,
    Turn,
)
from dndc.gm.templates import TemplateError, load_template, render, render_template

__all__ = [
    "CampaignContext",
    "CanonEntry",
    "CanonLedger",
    "CanonScope",
    "DEFAULT_WINDOW",
    "GMPromptBuilder",
    "PartyMember",
    "SCAFFOLDING_TEMPLATES",
    "TemplateError",
    "Turn",
    "load_template",
    "render",
    "render_entries",
    "render_template",
]
