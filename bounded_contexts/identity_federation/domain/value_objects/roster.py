"""assay's answer to "who may use this app right now" (ADR-0040).

A value mirroring exactly the shape returned by the endpoint of idp ADR-0057. It carries only ``sub`` and
the status, no profile (attribute copies are passed on every login; ADR-0038).

⚠ **Unknown statuses fall back to "leave alone".** If, on the day assay adds a fourth status, this side
read "unknown = stop", **everyone would be stopped**. Do not stop people on a value we cannot read.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RosterState(Enum):
    """How one person on the roster is treated. Split into three by **the action the RP takes** (idp ADR-0057)."""

    #: May use it now.
    ALLOWED = "allowed"
    #: Present in assay but cannot use it now. ⚠ **Keep the link** (if restored over there, SSO works as is).
    BLOCKED = "blocked"
    #: Not present in this assay tenant (= gone). The link may be dropped too.
    UNKNOWN = "unknown"
    #: ⚠ assay returned **a value we do not know**, or not on the roster. Do nothing.
    UNRECOGNISED = ""

    @classmethod
    def of(cls, value: str) -> RosterState:
        for state in cls:
            if state is not cls.UNRECOGNISED and state.value == value:
                return state
        return cls.UNRECOGNISED

    @property
    def ends_sessions(self) -> bool:
        """Whether this status means "no longer allow use of the SSO session"."""
        return self in {RosterState.BLOCKED, RosterState.UNKNOWN}

    @property
    def drops_the_link(self) -> bool:
        """Whether the link (the ``federated_identities`` row) may be dropped too.

        ⚠ **Do not drop the link of someone who is merely stopped.** Dropping it would make the person
        link again when restored over there (per ADR-0036 it can only be created by the person's own action).
        """
        return self is RosterState.UNKNOWN


@dataclass(frozen=True)
class RosterEntry:
    """One roster row."""

    subject: str
    state: RosterState

    @classmethod
    def of(cls, payload: dict[str, object]) -> RosterEntry | None:
        """Build from one element of the response. ``None`` if ``sub`` cannot be read."""
        subject = payload.get("sub")
        state = payload.get("state")
        if not isinstance(subject, str) or not subject:
            return None
        return cls(subject=subject, state=RosterState.of(state if isinstance(state, str) else ""))


@dataclass(frozen=True)
class Roster:
    """The roster received in a single query.

    ⚠ **Do not represent "could not look up" with this type.** On failure, stop with an exception and
    skip reconciliation altogether -- if indistinguishable from an empty roster, merely assay misbehaving
    stops everyone (ADR-0040).
    """

    entries: tuple[RosterEntry, ...]

    def state_of(self, subject: str) -> RosterState:
        """Status of that ``sub``. ⚠ **A `sub` not on the roster is `UNRECOGNISED`** (= leave alone)."""
        for entry in self.entries:
            if entry.subject == subject:
                return entry.state
        return RosterState.UNRECOGNISED


__all__ = ["Roster", "RosterEntry", "RosterState"]
