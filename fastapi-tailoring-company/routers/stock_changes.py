from fastapi import APIRouter, HTTPException, Body, Query
from mongo.mongo_service import MongoDBService
import logging
from bson import ObjectId
from typing import List, Optional
from models.stock_change import StockChange
from models.paginated_response import PaginatedResponse
from datetime import datetime

router = APIRouter(
    prefix="/stock-changes",
    tags=["stock-changes"]
)

logger = logging.getLogger(__name__)
connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

@router.get("/all", response_model=List[StockChange])
async def get_stock_changes(
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    startDate: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
    endDate: Optional[datetime] = Query(None, description="Filter by end date (ISO format)")
):
    try:
        conditions = {}
        
        if startDate or endDate:
            date_filter = {}
            if startDate:
                date_filter["$gte"] = startDate
            if endDate:
                date_filter["$lte"] = endDate
            if date_filter:
                conditions["date"] = date_filter
        
        result = await mongodb_service.find_with_pagination(
            collection_name='stock_changes',
            skip=skip,
            limit=limit,
            conditions=conditions
        )
        
        logger.info(f"Retrieved {len(result['data'])} stock changes with pagination")
        return result['data']
    except Exception as e:
        logger.error(f"Error retrieving stock changes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/material/{material_id}/all", response_model=List[StockChange])
async def get_stock_changes_by_material(
    material_id: str,
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    startDate: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
    endDate: Optional[datetime] = Query(None, description="Filter by end date (ISO format)")
):
    try:
        conditions = {"material_id": material_id}
        
        if startDate or endDate:
            date_filter = {}
            if startDate:
                date_filter["$gte"] = startDate
            if endDate:
                date_filter["$lte"] = endDate
            if date_filter:
                conditions["date"] = date_filter
        
        result = await mongodb_service.find_with_pagination(
            collection_name='stock_changes',
            skip=skip,
            limit=limit,
            conditions=conditions
        )
        
        logger.info(f"Retrieved {len(result['data'])} stock changes for material {material_id} with pagination")
        return result['data']
    except Exception as e:
        logger.error(f"Error retrieving stock changes for material {material_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=StockChange)
async def create_stock_change(stock_change: StockChange = Body(...)):
    try:
        # Ensure total_value is calculated correctly
        stock_change.total_value = stock_change.quantity * stock_change.price_at_time
        
        # Insert into database
        doc = stock_change.model_dump(by_alias=True, exclude={"id"})
        stock_change_id = await mongodb_service.insert_one(
            collection_name='stock_changes',
            document=doc
        )
        
        # Get the created document
        created_stock_change = await mongodb_service.find_one(
            collection_name='stock_changes',
            query={"_id": ObjectId(stock_change_id)}
        )
        
        if not created_stock_change:
            raise HTTPException(status_code=500, detail="Error retrieving the created stock change")
            
        logger.info(f"Stock change created with ID: {stock_change_id}")
        return created_stock_change
    except Exception as e:
        logger.error(f"Error creating stock change: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/id/{stock_change_id}", response_model=StockChange)
async def get_stock_change(stock_change_id: str):
    try:
        stock_change = await mongodb_service.find_one(
            collection_name='stock_changes',
            query={"_id": ObjectId(stock_change_id)}
        )
        if stock_change is None:
            raise HTTPException(status_code=404, detail="Stock change not found")
            
        logger.info(f"Retrieved stock change with ID: {stock_change_id}")
        return stock_change
    except Exception as e:
        logger.error(f"Error retrieving stock change {stock_change_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/id/{stock_change_id}")
async def delete_stock_change(stock_change_id: str):
    try:
        deleted_count = await mongodb_service.delete_one(
            collection_name='stock_changes',
            query={"_id": ObjectId(stock_change_id)}
        )
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="Stock change not found")
            
        logger.info(f"Stock change deleted with ID: {stock_change_id}")
        return {"message": "Stock change deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting stock change {stock_change_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/paginated", response_model=PaginatedResponse[StockChange])
async def get_stock_changes_paginated(
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    startDate: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
    endDate: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
    materialId: Optional[str] = Query(None, description="Filter by material ID")
):
    try:
        conditions = {}
        
        if materialId:
            conditions["material_id"] = materialId
            
        if startDate or endDate:
            date_filter = {}
            if startDate:
                date_filter["$gte"] = startDate
            if endDate:
                date_filter["$lte"] = endDate
            if date_filter:
                conditions["date"] = date_filter
        
        result = await mongodb_service.find_with_pagination(
            collection_name='stock_changes',
            skip=skip,
            limit=limit,
            conditions=conditions
        )
        
        logger.info(f"Retrieved {len(result['data'])} stock changes with pagination info")
        return result
    except Exception as e:
        import traceback
        logger.error(f"Error retrieving paginated stock changes: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        empty_result = {
            "data": [],
            "pagination": {
                "total": 0,
                "skip": skip,
                "limit": limit,
                "hasMore": False
            }
        }
        return empty_result

@router.get("/material/{material_id}/paginated", response_model=PaginatedResponse[StockChange])
async def get_stock_changes_by_material_paginated(
    material_id: str,
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    startDate: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
    endDate: Optional[datetime] = Query(None, description="Filter by end date (ISO format)")
):
    try:
        conditions = {"material_id": material_id}
        
        if startDate or endDate:
            date_filter = {}
            if startDate:
                date_filter["$gte"] = startDate
            if endDate:
                date_filter["$lte"] = endDate
            if date_filter:
                conditions["date"] = date_filter
        
        result = await mongodb_service.find_with_pagination(
            collection_name='stock_changes',
            skip=skip,
            limit=limit,
            conditions=conditions
        )
        
        logger.info(f"Retrieved {len(result['data'])} stock changes for material {material_id} with pagination info")
        return result
    except Exception as e:
        import traceback
        logger.error(f"Error retrieving paginated stock changes for material {material_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Return empty result instead of raising an exception
        empty_result = {
            "data": [],
            "pagination": {
                "total": 0,
                "skip": skip,
                "limit": limit,
                "hasMore": False
            }
        }
        return empty_result
