from pydantic import BaseModel, Field, Tuple
from typing import List, Optional, Dict
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


# Enums
from enum import Enum


class StatusEnum(str, Enum):
    placed = "Placed"
    offer_placed = "OfferPlaced"
    accepted = "Accepted"
    in_progress = "InProgress"
    finished = "Finished"
    declined = "Declined"


class ModelTypeEnum(str, Enum):
    monthly_predictions = "MonthlyPredictions"
    price_predictions = "PricePredictions"
    material_price_prediction = "MaterialPricePrediction"

class TypeEnum(str, Enum):
    dresses = "Dresses"
    bed_covers = "BedCovers"
    overalls = "Overalls"


# Models
class Materials(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    price: float
    picture: Optional[str] 
    unit: str
    updated: datetime
    is_used_in_ai: bool = False

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Orders(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    description: str
    product_id: Optional[PyObjectId]
    image_reference: Optional[str]  
    final_image: Optional[str]  
    status: StatusEnum
    pickup_time: datetime
    finished_order_time: Optional[datetime]

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Products(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    workmanship: float
    materials: List[Tuple[int, str]] 
    materials_price: float
    time_taken: int
    type: TypeEnum
    is_used_in_ai: bool = False

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class MonthOrdersPredictions(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    year: int
    months: Dict[str, int]  
    model_version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class MaterialsPriceUpdated(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    materialId: Optional[PyObjectId]
    price: float
    updatedAt: datetime
    isLatest: bool
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}