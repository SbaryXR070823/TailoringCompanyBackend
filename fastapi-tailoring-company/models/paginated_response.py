from typing import List, Generic, TypeVar, Dict, Any
from pydantic import BaseModel, ConfigDict

T = TypeVar('T')

class PaginationInfo(BaseModel):
    total: int
    skip: int
    limit: int
    hasMore: bool
    
    model_config = ConfigDict(extra='ignore')

class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    pagination: PaginationInfo
    
    model_config = ConfigDict(extra='ignore')