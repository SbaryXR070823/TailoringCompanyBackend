from datetime import datetime
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field

class StockChangeType:
    INITIAL_STOCK = "InitialStock"
    STOCK_UPDATE = "StockUpdate"
    ORDER_UPDATE = "OrderUpdate"

class StockChange(BaseModel):
    id: Optional[str] = Field(alias="_id", default=None)
    material_id: str
    change_type: str
    date: datetime = Field(default_factory=datetime.now)
    quantity: float
    price_at_time: float
    total_value: float    
    model_config = {
        'json_encoders': {ObjectId: str},
        'populate_by_name': True
    }
