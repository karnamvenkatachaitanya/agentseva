"""Product-catalog service.

Shared by the REST API (Store Catalog tab) and the agent tools
(``search_product_catalog`` + item-priced orders). All monetary maths uses the
real ``price_inr`` from the database so the agent never invents amounts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import SessionLocal
from app.models.product import Product

# 8–10 sample merchant products (Kirana goods, food, and SaaS) seeded if empty.
_CATALOG_SEED_LOCK_ID = 1_151_736_582
SEED_CATALOG: List[Dict[str, Any]] = [
    {"name": "Amul Taaza Toned Milk (1L)", "description": "Fresh toned milk, 3% fat.",
     "price_inr": 54, "category": "Dairy", "stock_quantity": 65, "image_url": ""},
    {"name": "Aashirvaad Shudh Chakki Atta (5kg)", "description": "Whole wheat atta.",
     "price_inr": 285, "category": "Staples", "stock_quantity": 40, "image_url": ""},
    {"name": "Tata Salt Iodised (1kg)", "description": "Vacuum evaporated iodised salt.",
     "price_inr": 28, "category": "Staples", "stock_quantity": 120, "image_url": ""},
    {"name": "Fortune Sunflower Oil (1L)", "description": "Refined sunflower cooking oil.",
     "price_inr": 145, "category": "Oils", "stock_quantity": 60, "image_url": ""},
    {"name": "Parle-G Glucose Biscuits (800g)", "description": "Classic glucose biscuits.",
     "price_inr": 90, "category": "Snacks", "stock_quantity": 80, "image_url": ""},
    {"name": "Brooke Bond Red Label Tea (500g)", "description": "Strong CTC black tea.",
     "price_inr": 260, "category": "Beverages", "stock_quantity": 45, "image_url": ""},
    {"name": "Maggi 2-Minute Noodles (12-pack)", "description": "Masala instant noodles.",
     "price_inr": 168, "category": "Snacks", "stock_quantity": 70, "image_url": ""},
    {"name": "Surf Excel Detergent Powder (1kg)", "description": "Tough-stain detergent.",
     "price_inr": 140, "category": "Household", "stock_quantity": 55, "image_url": ""},
    {"name": "AgentSeva Pro (Monthly SaaS)", "description": "AI merchant suite subscription.",
     "price_inr": 499, "category": "Digital", "stock_quantity": 999, "image_url": ""},
    {"name": "Cloud Backup 100GB (Monthly SaaS)", "description": "Encrypted cloud backup.",
     "price_inr": 199, "category": "Digital", "stock_quantity": 999, "image_url": ""},
]


def seed_catalog_if_empty(session_factory: Optional[sessionmaker] = None) -> int:
    """Insert the sample catalog once, including during concurrent first boots.

    Returns the number of products inserted (0 if it was already populated).
    """
    factory = session_factory or SessionLocal
    with factory() as session:
        with session.begin():
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                # Serialize the tiny check-and-insert transaction across Autoscale
                # instances. The transaction-scoped lock is released on commit.
                session.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": _CATALOG_SEED_LOCK_ID},
                )
            existing = session.execute(select(Product.id).limit(1)).first()
            if existing:
                return 0
            session.add_all([Product(**row) for row in SEED_CATALOG])
            return len(SEED_CATALOG)


def search_products(
    session: Session, query: Optional[str] = None, category: Optional[str] = None, limit: int = 50
) -> List[Product]:
    """Search products by name/description substring and optional category."""
    stmt = select(Product)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.description.ilike(like)))
    if category:
        stmt = stmt.where(Product.category.ilike(category.strip()))
    stmt = stmt.order_by(Product.name.asc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def get_products_by_ids(session: Session, ids: List[int]) -> Dict[int, Product]:
    """Return a ``{id: Product}`` map for the given ids."""
    if not ids:
        return {}
    rows = session.execute(select(Product).where(Product.id.in_(ids))).scalars().all()
    return {p.id: p for p in rows}


def price_order_items(session: Session, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute an order total from real catalog prices.

    ``items`` is ``[{"product_id": int, "quantity": int}, ...]``.
    Returns ``{"ok", "total_inr", "line_items", "errors"}``.
    """
    errors: List[str] = []
    line_items: List[Dict[str, Any]] = []
    ids = []
    for it in items:
        try:
            ids.append(int(it["product_id"]))
        except (KeyError, TypeError, ValueError):
            errors.append(f"invalid item entry: {it!r}")
    catalog = get_products_by_ids(session, ids)

    total = 0.0
    for it in items:
        try:
            pid = int(it["product_id"])
            qty = int(it.get("quantity", 1))
        except (KeyError, TypeError, ValueError):
            continue
        if qty <= 0:
            errors.append(f"quantity must be positive for product {it.get('product_id')}")
            continue
        product = catalog.get(pid)
        if product is None:
            errors.append(f"product_id {pid} not found in catalog")
            continue
        line_total = round(product.price_inr * qty, 2)
        total += line_total
        line_items.append({
            "product_id": pid, "name": product.name, "quantity": qty,
            "unit_price": product.price_inr, "line_total": line_total,
        })

    return {
        "ok": not errors and bool(line_items),
        "total_inr": round(total, 2),
        "line_items": line_items,
        "errors": errors,
    }
