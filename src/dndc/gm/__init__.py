"""GM brain: prompt assembly, canon ledger, NPC gating, threshold escalation."""

from dndc.gm.canon import CanonEntry, CanonLedger, CanonScope, render_entries
from dndc.gm.checkrequest import CheckRequest, CheckRequestError, find_check_request
from dndc.gm.context import (
    DEFAULT_WINDOW,
    SCAFFOLDING_TEMPLATES,
    CampaignContext,
    GMPromptBuilder,
    PartyMember,
    Turn,
)
from dndc.gm.creation import CreationPromptBuilder, render_options
from dndc.gm.proposal import Proposal, ProposalError, find_facts, find_proposal, strip_tags
from dndc.gm.templates import TemplateError, load_template, render, render_template

__all__ = [
    "CampaignContext",
    "CanonEntry",
    "CanonLedger",
    "CanonScope",
    "CheckRequest",
    "CheckRequestError",
    "CreationPromptBuilder",
    "DEFAULT_WINDOW",
    "GMPromptBuilder",
    "PartyMember",
    "Proposal",
    "ProposalError",
    "SCAFFOLDING_TEMPLATES",
    "TemplateError",
    "Turn",
    "find_check_request",
    "find_facts",
    "find_proposal",
    "load_template",
    "render",
    "render_entries",
    "render_options",
    "render_template",
    "strip_tags",
]
