"""The LAN front end (Phase 6).

Kept apart from `game/` deliberately. Everything here is about *showing* a campaign to a
device; nothing here may decide what happens in one. The turn loop is `game/session.py`
and there is exactly one of it (P6.1).
"""

from dndc.web.view import (
    MemberView,
    SpokenView,
    TableView,
    TurnView,
    table_view,
)

__all__ = [
    "MemberView",
    "SpokenView",
    "TableView",
    "TurnView",
    "table_view",
]
