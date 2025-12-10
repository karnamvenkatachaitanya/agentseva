from pydantic import BaseModel
from typing import List, Optional

class OrderItem(BaseModel):
    item: str
    quantity: int
    customization: Optional[str] = None
    spice_level: Optional[str] = None
    addons: List[str] = []
    notes: Optional[str] = None

class Order(BaseModel):
    items: List[OrderItem]
    total_price: Optional[float] = 0.0

class VoiceQuery(BaseModel):
    text: str
    session_id: Optional[str] = "default"

class APIResponse(BaseModel):
    response_text: str
    audio_base64: Optional[str] = None
    order: Optional[Order] = None
