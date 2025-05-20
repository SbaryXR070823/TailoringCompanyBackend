from fastapi import APIRouter, HTTPException, Body
from mongo.mongo_service import MongoDBService
import logging
from bson import ObjectId
from typing import List
from models.stock_change import StockChange

router = APIRouter(
    prefix="/stock-changes",
    tags=["stock-changes"]
)

logger = logging.getLogger(__name__)
connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

@router.get("/", response_model=List[StockChange])
async def get_stock_changes():
    try:
        stock_changes = await mongodb_service.find_all(collection_name='stock_changes')
        logger.info(f"Retrieved {len(stock_changes)} stock changes")
        return stock_changes
    except Exception as e:
        logger.error(f"Error retrieving stock changes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/material/{material_id}", response_model=List[StockChange])
async def get_stock_changes_by_material(material_id: str):
    try:
        stock_changes = await mongodb_service.find_with_conditions(
            collection_name='stock_changes', 
            conditions={"material_id": material_id}
        )
        logger.info(f"Retrieved {len(stock_changes)} stock changes for material {material_id}")
        return stock_changes
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

@router.get("/{stock_change_id}", response_model=StockChange)
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

@router.delete("/{stock_change_id}")
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
