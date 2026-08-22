from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from proofline.contracts import CreateSessionRequest, DeletionReceipt, SessionStatus


class SessionStore:
    """Process-local metadata only; uploaded file bytes are not accepted or retained here."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionStatus] = {}
        self._lock = Lock()

    def create(self, request: CreateSessionRequest) -> SessionStatus:
        session_id = f"session-{uuid4()}"
        status = SessionStatus(
            session_id=session_id,
            state="accepted",
            input=request.input,
            cached_output_status="not_checked",
            fallback_disclosure=(
                "No cached output has been selected. Processing adapters are not implemented "
                "in this contract-first service."
            ),
        )
        with self._lock:
            self._sessions[session_id] = status
        return status

    def get(self, session_id: str) -> SessionStatus | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> DeletionReceipt | None:
        with self._lock:
            deleted = self._sessions.pop(session_id, None)
        if deleted is None:
            return None
        return DeletionReceipt(
            session_id=session_id,
            deleted_at=datetime.now(UTC),
            disclosure=(
                "Deleted process-local session metadata only. This endpoint never accepted or "
                "stored document bytes and makes no claim about external source systems."
            ),
        )
