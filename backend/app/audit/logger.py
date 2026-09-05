"""Append-only transaction audit logging (``transaction_audit_logs``).

Every state change and money-related tool invocation writes an **immutable**
row *before* the external call (``status="initiated"``) and another *after* it
completes (``status="success" | "failed" | "error"``). The two rows share a
``trace_id`` so a single logical call is a before/after pair, and the whole
decision tree for a session can be replayed in order.

The table is append-only *by construction*: the public API exposes only
inserts (:meth:`AuditLogger.record`, :meth:`AuditLogger.trace`) and reads
(:meth:`AuditLogger.get_traces`). There is no update or delete path.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.db.base import Base, SessionLocal

logger = logging.getLogger(__name__)


def _utcnow() -> _dt.datetime:
    """Timezone-aware UTC timestamp."""
    return _dt.datetime.now(_dt.timezone.utc)


def _dumps(value: Any) -> Optional[str]:
    """Serialise a payload to compact JSON, or ``None`` if not provided."""
    if value is None:
        return None
    return json.dumps(value, default=str, sort_keys=True, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# ORM model
# --------------------------------------------------------------------------- #


class TransactionAuditLog(Base):
    """Immutable audit record for one before/after step of a tool call."""

    __tablename__ = "transaction_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timestamp: Mapped[_dt.datetime] = mapped_column(default=_utcnow, nullable=False)
    user_intent: Mapped[str] = mapped_column(Text, default="", nullable=False)
    agent_reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tool_called: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    payload_sent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def to_schema(self) -> "AuditTraceOut":
        """Convert this row into its serialisable Pydantic form."""
        return AuditTraceOut(
            id=self.id,
            trace_id=self.trace_id,
            session_id=self.session_id,
            timestamp=self.timestamp.isoformat(),
            user_intent=self.user_intent,
            agent_reasoning=self.agent_reasoning,
            tool_called=self.tool_called,
            payload_sent=_loads(self.payload_sent),
            api_response=_loads(self.api_response),
            status=self.status,
            latency_ms=self.latency_ms,
        )


def _loads(raw: Optional[str]) -> Optional[Any]:
    """Parse a JSON column back to a Python object, tolerating bad data."""
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}


# --------------------------------------------------------------------------- #
# Output schema
# --------------------------------------------------------------------------- #


class AuditTraceOut(BaseModel):
    """Serialised audit record returned by read APIs."""

    model_config = ConfigDict(extra="forbid")

    id: int
    trace_id: str
    session_id: str
    timestamp: str
    user_intent: str
    agent_reasoning: str
    tool_called: str
    payload_sent: Optional[Any] = None
    api_response: Optional[Any] = None
    status: str
    latency_ms: Optional[int] = None


# --------------------------------------------------------------------------- #
# Trace span (before/after helper)
# --------------------------------------------------------------------------- #


class TraceSpan:
    """Handle yielded by :meth:`AuditLogger.trace` to attach the API response."""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.response: Optional[Any] = None
        self.status: Optional[str] = None

    def set_response(self, response: Any, status: str = "success") -> None:
        """Record the external API response and final status for the 'after' row."""
        self.response = response
        self.status = status


# --------------------------------------------------------------------------- #
# Logger
# --------------------------------------------------------------------------- #


class AuditLogger:
    """Writes and reads the append-only ``transaction_audit_logs`` table."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    def record(
        self,
        session_id: str,
        tool_called: str,
        status: str,
        *,
        trace_id: Optional[str] = None,
        user_intent: str = "",
        agent_reasoning: str = "",
        payload_sent: Optional[Any] = None,
        api_response: Optional[Any] = None,
        latency_ms: Optional[int] = None,
    ) -> AuditTraceOut:
        """Append a single immutable audit row and return it."""
        entry = TransactionAuditLog(
            trace_id=trace_id or uuid.uuid4().hex,
            session_id=session_id,
            user_intent=user_intent,
            agent_reasoning=agent_reasoning,
            tool_called=tool_called,
            payload_sent=_dumps(payload_sent),
            api_response=_dumps(api_response),
            status=status,
            latency_ms=latency_ms,
        )
        with self._session_factory() as session:
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry.to_schema()

    @contextmanager
    def trace(
        self,
        session_id: str,
        tool_called: str,
        payload_sent: Optional[Any] = None,
        *,
        user_intent: str = "",
        agent_reasoning: str = "",
    ) -> Iterator[TraceSpan]:
        """Context manager that writes an immutable row before *and* after a call.

        Usage::

            with audit.trace(session_id, "generate_payment_link", payload) as span:
                resp = call_external_api()
                span.set_response(resp, status="success")

        On enter, a ``status="initiated"`` row is written. On normal exit, an
        ``after`` row is written with the measured latency and the response set
        via :meth:`TraceSpan.set_response` (defaulting to ``"success"``). If the
        block raises, an ``status="error"`` row is written and the exception is
        re-raised.
        """
        trace_id = uuid.uuid4().hex
        self.record(
            session_id, tool_called, "initiated",
            trace_id=trace_id, user_intent=user_intent, agent_reasoning=agent_reasoning,
            payload_sent=payload_sent,
        )
        span = TraceSpan(trace_id)
        start = time.perf_counter()
        try:
            yield span
        except Exception as exc:  # noqa: BLE001 — record then propagate
            latency = int((time.perf_counter() - start) * 1000)
            self.record(
                session_id, tool_called, "error",
                trace_id=trace_id, user_intent=user_intent, agent_reasoning=agent_reasoning,
                payload_sent=payload_sent, api_response={"error": str(exc)}, latency_ms=latency,
            )
            raise
        else:
            latency = int((time.perf_counter() - start) * 1000)
            self.record(
                session_id, tool_called, span.status or "success",
                trace_id=trace_id, user_intent=user_intent, agent_reasoning=agent_reasoning,
                payload_sent=payload_sent, api_response=span.response, latency_ms=latency,
            )

    def get_traces(self, session_id: str) -> List[AuditTraceOut]:
        """Return the full ordered decision tree for a session."""
        with self._session_factory() as session:
            rows = session.execute(
                select(TransactionAuditLog)
                .where(TransactionAuditLog.session_id == session_id)
                .order_by(TransactionAuditLog.id.asc())
            ).scalars().all()
            return [row.to_schema() for row in rows]

    def get_recent(self, limit: int = 50) -> List[AuditTraceOut]:
        """Return the most recent audit records across all sessions (newest first)."""
        with self._session_factory() as session:
            rows = session.execute(
                select(TransactionAuditLog).order_by(TransactionAuditLog.id.desc()).limit(limit)
            ).scalars().all()
            return [row.to_schema() for row in rows]

    def aggregate_metrics(self) -> Dict[str, Any]:
        """Compute gateway-level metrics from the audit trail.

        Only *completed* rows (status != ``initiated``) count as processed
        transactions. "Money recovered" sums the ``amount_in_paise`` of every
        successful ``generate_payment_link`` call.
        """
        with self._session_factory() as session:
            rows = session.execute(select(TransactionAuditLog)).scalars().all()

        completed = [r for r in rows if r.status != "initiated"]
        succeeded = [r for r in completed if r.status == "success"]
        failed = [r for r in completed if r.status in ("failed", "error")]

        recovered_paise = 0
        for row in succeeded:
            if row.tool_called == "generate_payment_link":
                resp = _loads(row.api_response) or {}
                if isinstance(resp, dict):
                    recovered_paise += int(resp.get("amount_in_paise") or 0)

        processed = len(completed)
        failure_rate = round(len(failed) / processed, 4) if processed else 0.0
        return {
            "transactions_processed": processed,
            "transactions_succeeded": len(succeeded),
            "transactions_failed": len(failed),
            "failure_rate": failure_rate,
            "money_recovered_paise": recovered_paise,
            "money_recovered_inr": round(recovered_paise / 100, 2),
            "recovery_links_issued": sum(
                1 for r in succeeded if r.tool_called == "generate_payment_link"
            ),
        }


#: Process-wide default logger bound to the app database.
audit_logger = AuditLogger()
