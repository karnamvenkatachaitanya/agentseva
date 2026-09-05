"""Order-persistence service — shared by checkout, agent tools, and webhooks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.base import SessionLocal
from app.models.order import Order


def create_order(
    customer_name: str,
    customer_phone: str,
    items: List[Dict[str, Any]],
    total_amount: float,
    *,
    razorpay_order_id: Optional[str] = None,
    razorpay_payment_link_id: Optional[str] = None,
    payment_link: Optional[str] = None,
    status: str = "pending",
    session_factory: Optional[sessionmaker] = None,
) -> Dict[str, Any]:
    """Persist a new order row and return it as a dict."""
    factory = session_factory or SessionLocal
    with factory() as session:
        order = Order(
            customer_name=customer_name or "Guest",
            customer_phone=customer_phone or "",
            items=items,
            total_amount=total_amount,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_link_id=razorpay_payment_link_id,
            payment_link=payment_link,
            status=status,
        )
        session.add(order)
        session.commit()
        session.refresh(order)
        return order.to_dict()


def list_orders(session_factory: Optional[sessionmaker] = None, limit: int = 200) -> List[Dict[str, Any]]:
    """Return all orders, newest first."""
    factory = session_factory or SessionLocal
    with factory() as session:
        rows = session.execute(select(Order).order_by(Order.id.desc()).limit(limit)).scalars().all()
        return [o.to_dict() for o in rows]


def get_order(order_id: int, session_factory: Optional[sessionmaker] = None) -> Optional[Dict[str, Any]]:
    """Return a single order by id, or ``None``."""
    factory = session_factory or SessionLocal
    with factory() as session:
        order = session.get(Order, order_id)
        return order.to_dict() if order else None


def update_status(
    order_id: int,
    status: str,
    *,
    payment_link: Optional[str] = None,
    razorpay_payment_link_id: Optional[str] = None,
    session_factory: Optional[sessionmaker] = None,
) -> Optional[Dict[str, Any]]:
    """Update an order's status (and optionally its recovery link)."""
    factory = session_factory or SessionLocal
    with factory() as session:
        order = session.get(Order, order_id)
        if order is None:
            return None
        order.status = status
        if payment_link is not None:
            order.payment_link = payment_link
        if razorpay_payment_link_id is not None:
            order.razorpay_payment_link_id = razorpay_payment_link_id
        session.commit()
        session.refresh(order)
        return order.to_dict()


def update_status_by_razorpay(
    *,
    razorpay_order_id: Optional[str] = None,
    razorpay_payment_link_id: Optional[str] = None,
    status: str = "paid",
    razorpay_payment_id: Optional[str] = None,
    session_factory: Optional[sessionmaker] = None,
) -> Optional[Dict[str, Any]]:
    """Update an order matched by its Razorpay order id or payment-link id.

    Used by webhook handlers to reflect live payment state.
    """
    factory = session_factory or SessionLocal
    with factory() as session:
        order = None
        if razorpay_order_id:
            order = session.execute(
                select(Order).where(Order.razorpay_order_id == razorpay_order_id)
            ).scalars().first()
        if order is None and razorpay_payment_link_id:
            order = session.execute(
                select(Order).where(Order.razorpay_payment_link_id == razorpay_payment_link_id)
            ).scalars().first()
        if order is None:
            return None
        order.status = status
        if razorpay_payment_id:
            order.razorpay_payment_id = razorpay_payment_id
        session.commit()
        session.refresh(order)
        return order.to_dict()
