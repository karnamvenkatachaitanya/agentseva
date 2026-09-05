"""Product catalog REST API (Store Catalog tab): CRUD + search."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.db.base import SessionLocal
from app.models.product import Product
from app.services.catalog import search_products

router = APIRouter()


class ProductIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    price_inr: float = Field(gt=0)
    category: str = Field(default="", max_length=100)
    stock_quantity: int = Field(default=0, ge=0)
    image_url: str = Field(default="", max_length=500)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    price_inr: Optional[float] = Field(default=None, gt=0)
    category: Optional[str] = Field(default=None, max_length=100)
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    image_url: Optional[str] = Field(default=None, max_length=500)


@router.get("")
def list_products(
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    """List/search catalog products."""
    with SessionLocal() as session:
        return [p.to_dict() for p in search_products(session, query=query, category=category)]


@router.get("/categories")
def list_categories() -> List[str]:
    """Return the distinct set of product categories."""
    with SessionLocal() as session:
        rows = session.execute(select(Product.category).distinct()).scalars().all()
        return sorted({c for c in rows if c})


@router.get("/{product_id}")
def get_product(product_id: int) -> Dict[str, Any]:
    with SessionLocal() as session:
        product = session.get(Product, product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        return product.to_dict()


@router.post("", status_code=201)
def create_product(body: ProductIn) -> Dict[str, Any]:
    with SessionLocal() as session:
        product = Product(**body.model_dump())
        session.add(product)
        session.commit()
        session.refresh(product)
        return product.to_dict()


@router.put("/{product_id}")
def update_product(product_id: int, body: ProductUpdate) -> Dict[str, Any]:
    with SessionLocal() as session:
        product = session.get(Product, product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        for key, value in body.model_dump(exclude_none=True).items():
            setattr(product, key, value)
        session.commit()
        session.refresh(product)
        return product.to_dict()


@router.delete("/{product_id}")
def delete_product(product_id: int) -> Dict[str, Any]:
    with SessionLocal() as session:
        product = session.get(Product, product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        session.delete(product)
        session.commit()
        return {"deleted": product_id}
