"""Orders & Recovery REST API.

* ``GET  /orders``               — list all orders with live status.
* ``POST /orders/checkout``      — price a cart from the real catalog, create a
                                   Razorpay payment link, and persist the order.
* ``POST /orders/{id}/recover``  — run the revenue-recovery workflow for an order.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.agent.recovery import CheckoutSnapshot, revenue_recovery_engine
from app.db.base import SessionLocal
from app.services import orders as orders_service
from app.services.catalog import price_order_items
from app.tools.razorpay_tools import razorpay_tools

router = APIRouter()


class CartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: int
    quantity: int = Field(gt=0, le=999)


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_name: str = Field(min_length=1, max_length=120)
    customer_phone: str = Field(min_length=8, max_length=20)
    items: List[CartItem] = Field(min_length=1)


@router.get("")
def list_orders() -> List[Dict[str, Any]]:
    """Return all orders, newest first."""
    return orders_service.list_orders()


@router.post("/checkout", status_code=201)
def checkout(body: CheckoutRequest) -> Dict[str, Any]:
    """Price the cart from the catalog and generate a Razorpay payment link."""
    raw_items = [it.model_dump() for it in body.items]
    with SessionLocal() as session:
        priced = price_order_items(session, raw_items)
    if not priced["ok"]:
        raise HTTPException(status_code=400, detail={"message": "cart pricing failed", **priced})

    description = f"AgentSeva order — {len(priced['line_items'])} item(s)"
    result = razorpay_tools.generate_payment_link(
        amount=priced["total_inr"],
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        description=description,
        items=raw_items,
    )
    if result.get("status") != "success":
        raise HTTPException(status_code=502, detail={"message": "payment link failed", **result})
    return {
        "status": "success",
        "order": result.get("order"),
        "payment_link": result.get("short_url"),
        "total_inr": priced["total_inr"],
        "line_items": priced["line_items"],
    }


@router.post("/{order_id}/recover")
def recover_order(order_id: int) -> Dict[str, Any]:
    """Run the revenue-recovery workflow for a specific order."""
    order = orders_service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")

    snapshot = CheckoutSnapshot(
        session_id=f"order-{order_id}",
        order_id=order.get("razorpay_order_id") or f"order-{order_id}",
        amount_inr=float(order["total_amount"]),
        customer_name=order.get("customer_name") or "Valued Customer",
        customer_phone=order.get("customer_phone") or "+910000000000",
        last_stage="payment",
        idle_seconds=120,
        payment_attempted=True,
    )
    recovery = revenue_recovery_engine.recover_dropped_checkout(snapshot)

    updated = order
    if recovery.status.value == "recovered_link_issued":
        updated = orders_service.update_status(
            order_id, "recovered", payment_link=recovery.payment_link
        ) or order

    return {"order": updated, "recovery": recovery.model_dump()}
