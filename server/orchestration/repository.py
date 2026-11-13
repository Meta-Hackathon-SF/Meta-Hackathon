"""Production persistence boundary, deliberately unconfigured until privacy ACK.

An implementation must atomically recheck current consent, membership, answers,
blocks and cycle revision before committing formation. A provider call must never
run inside that transaction. No in-memory production fallback is supplied.
"""

from typing import Protocol

from server.orchestration.wire import FormationSuccess, WeeklyCycle


class FormationStore(Protocol):
    async def claim(self, cycle_id: str) -> dict | None:
        """Lease one pending job; return a private, versioned authorized snapshot."""
        ...

    async def commit(self, job: dict, result: FormationSuccess) -> None:
        """CAS lease + current privacy/cycle revision; persist atomically, once."""
        ...

    async def fail(self, job: dict, code: str) -> None:
        """Persist only a stable error code; bounded attempts/backoff, never text."""
        ...

    async def cycle(self, cycle_id: str) -> WeeklyCycle: ...
