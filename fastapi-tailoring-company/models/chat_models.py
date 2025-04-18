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

class Message(BaseModel):
    id: Annotated[ObjectId, BeforeValidator(validate_object_id)] = Field(default_factory=ObjectId, alias="_id")
    sender_id: str
    sender_name: str
    sender_role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_read: bool = False

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }

class ChatThread(BaseModel):
    id: Annotated[ObjectId, BeforeValidator(validate_object_id)] = Field(default_factory=ObjectId, alias="_id")
    user_id: str
    admin_id: Optional[str] = None
    messages: List[Message] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }
