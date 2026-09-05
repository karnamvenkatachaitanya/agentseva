"""Tests for the append-only audit trail."""

from __future__ import annotations

from app.engine.audit import AuditLogger
from app.engine.schemas import ActionType


def test_records_are_sequenced_per_session(audit_logger: AuditLogger):
    audit_logger.record("s1", ActionType.INTENT, "start")
    audit_logger.record("s1", ActionType.REASONING, "thinking")
    audit_logger.record("s1", ActionType.OUTPUT, "done")
    trail = audit_logger.get_trail("s1")
    assert [r.sequence for r in trail] == [1, 2, 3]
    assert [r.action_type for r in trail] == [
        ActionType.INTENT, ActionType.REASONING, ActionType.OUTPUT
    ]


def test_sessions_are_isolated(audit_logger: AuditLogger):
    audit_logger.record("a", ActionType.INTENT, "a1")
    audit_logger.record("b", ActionType.INTENT, "b1")
    audit_logger.record("b", ActionType.OUTPUT, "b2")
    assert len(audit_logger.get_trail("a")) == 1
    assert len(audit_logger.get_trail("b")) == 2


def test_payload_roundtrips(audit_logger: AuditLogger):
    audit_logger.record("s", ActionType.TOOL_EXECUTION, "order", {"amount": 5000, "currency": "INR"})
    record = audit_logger.get_trail("s")[0]
    assert record.payload == {"amount": 5000, "currency": "INR"}


def test_non_serialisable_payload_is_coerced(audit_logger: AuditLogger):
    class Weird:
        def __str__(self) -> str:
            return "weird-object"

    audit_logger.record("s", ActionType.ERROR, "boom", {"obj": Weird()})
    record = audit_logger.get_trail("s")[0]
    assert record.payload["obj"] == "weird-object"


def test_empty_trail_returns_empty_list(audit_logger: AuditLogger):
    assert audit_logger.get_trail("does-not-exist") == []
