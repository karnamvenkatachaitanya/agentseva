"""Order model — ties a customer purchase to its Razorpay lifecycle."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


#: Allowed order statuses.
ORDER_STATUSES = ("pending", "paid", "failed", "recovered")


class Order(Base):
    """A customer order and its Razorpay payment state."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    # Line items: [{product_id, name, quantity, unit_price, line_total}]
    items: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    razorpay_payment_link_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    payment_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the order to a plain dict."""
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "items": self.items or [],
            "total_amount": self.total_amount,
            "razorpay_order_id": self.razorpay_order_id,
            "razorpay_payment_id": self.razorpay_payment_id,
            "razorpay_payment_link_id": self.razorpay_payment_link_id,
            "payment_link": self.payment_link,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
