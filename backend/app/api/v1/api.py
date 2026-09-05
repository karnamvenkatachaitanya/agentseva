from fastapi import APIRouter
from app.api.v1.endpoints import ai, audit, catalog, engine, orders, recovery

api_router = APIRouter()
api_router.include_router(ai.router, prefix="/ai", tags=["AI Services"])
api_router.include_router(catalog.router, prefix="/products", tags=["Product Catalog"])
api_router.include_router(orders.router, prefix="/orders", tags=["Orders & Recovery"])
api_router.include_router(engine.router, prefix="/engine", tags=["Agentic Commerce & Recovery"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit Traces"])
api_router.include_router(recovery.router, prefix="/recovery", tags=["Revenue Recovery"])
