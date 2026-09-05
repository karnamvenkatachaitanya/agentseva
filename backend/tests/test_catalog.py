"""Tests for catalog integration: search tool + item-priced orders from SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.services.catalog import price_order_items, search_products, seed_catalog_if_empty
from app.tools.razorpay_tools import RazorpayToolRegistry


@pytest.fixture()
def factory():
    """In-memory SQLite with the sample catalog seeded."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    Base.metadata.create_all(bind=engine)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    inserted = seed_catalog_if_empty(sf)
    assert inserted >= 8  # 8–10 sample products
    return sf


@pytest.fixture()
def registry(factory):
    """Mock Razorpay registry wired to the in-memory catalog DB."""
    return RazorpayToolRegistry(config=Settings(_env_file=None), session_factory=factory)


def test_seed_is_idempotent(factory):
    assert seed_catalog_if_empty(factory) == 0  # already seeded


def test_search_products_by_name(factory):
    with factory() as s:
        results = search_products(s, "milk")
    assert any("Milk" in p.name for p in results)


def test_search_tool_returns_products(registry):
    out = registry.search_product_catalog("atta")
    assert out["status"] == "success"
    assert out["count"] >= 1
    assert "price_inr" in out["products"][0]


def test_price_order_items_uses_real_prices(factory):
    with factory() as s:
        milk = search_products(s, "milk")[0]
        atta = search_products(s, "atta")[0]
        priced = price_order_items(s, [
            {"product_id": milk.id, "quantity": 2},
            {"product_id": atta.id, "quantity": 1},
        ])
    assert priced["ok"]
    assert priced["total_inr"] == round(milk.price_inr * 2 + atta.price_inr, 2)


def test_price_order_items_flags_missing_product(factory):
    with factory() as s:
        priced = price_order_items(s, [{"product_id": 99999, "quantity": 1}])
    assert not priced["ok"]
    assert priced["errors"]


def test_create_order_from_items_computes_total(registry, factory):
    with factory() as s:
        milk = search_products(s, "milk")[0]
    result = registry.create_order(items=[{"product_id": milk.id, "quantity": 3}], receipt_id="cat-1")
    assert result["status"] == "success"
    assert result["amount_in_paise"] == int(round(milk.price_inr * 3 * 100))
    assert result["db_order_id"] is not None  # order persisted
    assert len(result["line_items"]) == 1


def test_generate_payment_link_from_items(registry, factory):
    with factory() as s:
        atta = search_products(s, "atta")[0]
    result = registry.generate_payment_link(
        items=[{"product_id": atta.id, "quantity": 1}],
        customer_name="Asha", customer_phone="+919876543210", description="Cart",
    )
    assert result["status"] == "success"
    assert result["short_url"].startswith("https://")
    assert result["db_order_id"] is not None


def test_create_order_requires_amount_or_items(registry):
    result = registry.create_order(receipt_id="x")  # neither amount nor items
    assert result["status"] == "error"
    assert result["error"] == "validation_error"
