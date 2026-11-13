"""Client-generated idempotency key.

Keeps a double tap on mobile from recording twice in the ledger; unique per ledger
(``UNIQUE (ledger_id, idempotency_key)``). A collision is not an error: the existing
record is returned (ADR-0010).

One operation may write two rows (correction = reversal + re-record; ADR-0022).
Using the same key twice would make the second row reuse the first, so
:meth:`IdempotencyKey.for_step` derives a key per step. So that derived keys still
fit the limit, incoming keys are capped at :data:`MAX_BASE_LENGTH`.

:data:`STEP_SEPARATOR` is reserved for this split and must not appear in client keys
(rejected via :func:`is_derived`). The ledger has a single key space; if derived and
received keys could take the same form, an unrelated row would be mistaken for a
resend of the same operation.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_LENGTH = 64
STEP_SEPARATOR = "#"
MAX_STEP_LENGTH = 12
MAX_BASE_LENGTH = MAX_LENGTH - len(STEP_SEPARATOR) - MAX_STEP_LENGTH


@dataclass(frozen=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Idempotency key cannot be empty")
        if len(self.value) > MAX_LENGTH:
            raise ValueError(f"Idempotency key cannot exceed {MAX_LENGTH} characters")

    def for_step(self, step: str) -> IdempotencyKey:
        """The key for one step within a single operation.

        What matters is that a resent request yields the same value; steps only
        need to differ from each other.
        """
        if not 0 < len(step) <= MAX_STEP_LENGTH:
            raise ValueError(f"Idempotency step must be 1..{MAX_STEP_LENGTH} characters")
        if len(self.value) > MAX_BASE_LENGTH:
            raise ValueError(f"Idempotency key cannot exceed {MAX_BASE_LENGTH} characters to be split by step")
        return IdempotencyKey(f"{self.value}{STEP_SEPARATOR}{step}")


def is_derived(value: str) -> bool:
    """Whether the value has the shape of a per-step derived key.

    The separator is reserved for this split and never accepted from clients
    (rejected at the ``API``). If accepted, a client sending ``<key>#reversal``
    verbatim would collide with the reversal row a correction is about to write,
    and ``append`` would return an unrelated existing row.
    """
    return STEP_SEPARATOR in value


__all__ = [
    "MAX_BASE_LENGTH",
    "MAX_LENGTH",
    "MAX_STEP_LENGTH",
    "STEP_SEPARATOR",
    "IdempotencyKey",
    "is_derived",
]
