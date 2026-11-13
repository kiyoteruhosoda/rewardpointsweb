"""Output DTOs for display devices (ADR-0047)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class DisplayDTO:
    """One display device showing a family. 1 device = 1 account = 1 membership."""

    account_id: int
    membership_id: int
    family_id: int
    family_name: str
    #: Device name (e.g. "Living room"). It is listed under this name among the family's members too
    name: str
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class DisplayableFamilyDTO:
    """A family the operator can choose to display. Name only; no ledgers included."""

    id: int
    name: str


__all__ = ["DisplayDTO", "DisplayableFamilyDTO"]
