from datetime import datetime
from typing import List, Optional, Any, Annotated
from pydantic import BaseModel, Field, BeforeValidator
from bson import ObjectId

def validate_object_id(v: Any) -> ObjectId:
    if isinstance(v, ObjectId):
        return v
    if isinstance(v, str) and ObjectId.is_valid(v):
        return ObjectId(v)
    raise ValueError("Invalid ObjectId")

class ChatFile(BaseModel):
    id: Annotated[ObjectId, BeforeValidator(validate_object_id)] = Field(default_factory=ObjectId, alias="_id")
    filename: str
    content_type: str
    size: int  # in bytes
    storage_id: str  # GridFS file ID 
    uploaded_by: str
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }
