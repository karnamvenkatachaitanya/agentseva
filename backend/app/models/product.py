"""Product catalog model."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


class Product(Base):
    """A merchant catalog product."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price_inr: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="", index=True, nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the product to a plain dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price_inr": self.price_inr,
            "category": self.category,
            "stock_quantity": self.stock_quantity,
            "image_url": self.image_url,
            "in_stock": self.stock_quantity > 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
