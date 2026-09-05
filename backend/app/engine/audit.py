"""Append-only audit trail.

Every step the engine takes — intent, reasoning, guardrail verdict, tool
execution, output, error, recovery — is written as an immutable row to the
``audit_log`` table. The trail is *append-only by construction*: the public
API exposes only :meth:`AuditLogger.record` (INSERT) and read helpers. No
update or delete path is provided.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Any, Dict, List, Optional

from sqlalchemy import Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.db.base import Base, SessionLocal
from app.engine.schemas import ActionType, AuditRecordOut


def _utcnow() -> _dt.datetime:
    """Return a timezone-aware UTC timestamp."""
    return _dt.datetime.now(_dt.timezone.utc)


class AuditLog(Base):
    """Immutable, append-only audit record.

    ``payload`` is stored as a JSON string (portable across SQLite/PostgreSQL);
    it is (de)serialised via :mod:`json` so the column stays a plain ``TEXT``.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="engine")
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[_dt.datetime] = mapped_column(default=_utcnow, nullable=False)

    def to_schema(self) -> AuditRecordOut:
        """Convert this ORM row into its serialisable Pydantic form."""
        try:
            payload = json.loads(self.payload_json) if self.payload_json else {}
        except json.JSONDecodeError:
            payload = {"_raw": self.payload_json}
        return AuditRecordOut(
            id=self.id,
            session_id=self.session_id,
            sequence=self.sequence,
            action_type=ActionType(self.action_type),
            actor=self.actor,
            summary=self.summary,
            payload=payload,
            created_at=self.created_at.isoformat(),
        )


class AuditLogger:
    """Writes and reads the append-only audit trail.

    Parameters
    ----------
    session_factory:
        A SQLAlchemy ``sessionmaker``. Defaults to the app-wide
        :data:`app.db.base.SessionLocal`; tests inject an in-memory factory.
    """

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    def _next_sequence(self, session: Session, session_id: str) -> int:
        """Return the next 1-based sequence number for a logical session."""
        current_max = session.execute(
            select(func.max(AuditLog.sequence)).where(AuditLog.session_id == session_id)
        ).scalar_one_or_none()
        return (current_max or 0) + 1

    def record(
        self,
        session_id: str,
        action_type: ActionType,
        summary: str,
        payload: Optional[Dict[str, Any]] = None,
        actor: str = "engine",
    ) -> AuditRecordOut:
        """Append a single immutable step to the trail and return it.

        Payload values are JSON-serialised defensively: any non-serialisable
        object is coerced to ``str`` so logging can never crash the caller.
        """
        payload = payload or {}
        payload_json = json.dumps(payload, default=str, ensure_ascii=False)

        with self._session_factory() as session:
            entry = AuditLog(
                session_id=session_id,
                sequence=self._next_sequence(session, session_id),
                action_type=action_type.value,
                actor=actor,
                summary=summary[:500],
                payload_json=payload_json,
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry.to_schema()

    def get_trail(self, session_id: str) -> List[AuditRecordOut]:
        """Return every recorded step for ``session_id`` in insertion order."""
        with self._session_factory() as session:
            rows = session.execute(
                select(AuditLog)
                .where(AuditLog.session_id == session_id)
                .order_by(AuditLog.sequence.asc())
            ).scalars().all()
            return [row.to_schema() for row in rows]


#: Process-wide default logger bound to the app database.
audit_logger = AuditLogger()
