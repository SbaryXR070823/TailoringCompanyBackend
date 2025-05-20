from fastapi import APIRouter, HTTPException, Body
from mongo.mongo_service import MongoDBService
import logging
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StockUpdate(BaseModel):
    quantityChange: int 
    changeType: str

router = APIRouter()
logger = logging.getLogger(__name__)

connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

@router.get("/materials/")
async def get_materials():
    try:
        materials = await mongodb_service.find_all(collection_name='materials')
        logger.info(f"Retrieved {len(materials)} materials")
        return materials
    except Exception as e:
        logger.error(f"Error retrieving materials: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving materials")

@router.post("/materials/")
async def create_material(material: dict):
    if '_id' in material:
        del material['_id']
    
    material_id = await mongodb_service.insert_one(collection_name='materials', document=material)
    new_material = await mongodb_service.find_one(collection_name='materials', query={"_id": ObjectId(material_id)})

    if not new_material:
        raise HTTPException(status_code=500, detail="Error retrieving the created material")

    try:        
        stock_change = {
            "material_id": str(material_id),
            "change_type": "InitialStock",
            "quantity": material.get("stock", 0),
            "price_at_time": material.get("price", 0),
            "total_value": material.get("stock", 0) * material.get("price", 0),
            "date": datetime.utcnow()
        }
        await mongodb_service.insert_one(collection_name='stock_changes', document=stock_change)
    except Exception as e:
        logger.error(f"Error creating stock change record: {str(e)}")

    return new_material

@router.get("/materials/{material_id}")
async def get_material(material_id: str):
    material = await mongodb_service.find_one(collection_name='materials', query={"_id": ObjectId(material_id)})
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material

@router.put("/materials/{material_id}")
async def update_material(material_id: str, material: dict):
    # Remove _id from the material dictionary if it exists, mongo loves to throw errors for some a reason.......
    material.pop('_id', None)
    updated_material = await mongodb_service.update_one(
        collection_name='materials',
        query={"_id": ObjectId(material_id)},
        update=material
    )
    if not updated_material:
        raise HTTPException(status_code=404, detail="Material not found")
    return updated_material

@router.delete("/materials/{material_id}")
async def delete_material(material_id: str):
    deleted_count = await mongodb_service.delete_one(collection_name='materials', query={"_id": ObjectId(material_id)})
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"message": "Material deleted successfully"}

@router.patch("/materials/{material_id}/stock")
async def update_material_stock(material_id: str, stock_update: StockUpdate = Body(...)):
    """
    Update the stock quantity of a material
    
    - **material_id**: ID of the material to update
    - **quantityChange**: Amount to add to the stock (negative to decrease)
    - **changeType**: Type of change (StockUpdate or OrderUpdate)
    """
    try:
        material = await mongodb_service.find_one(collection_name='materials', query={"_id": ObjectId(material_id)})
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        
        current_stock = material.get("stock", 0)
        current_price = material.get("price", 0)
        
        new_stock = current_stock + stock_update.quantityChange
        
        if new_stock < 0:
            raise HTTPException(status_code=400, detail=f"Insufficient stock. Current: {current_stock}, Requested change: {stock_update.quantityChange}")
        
        result = await mongodb_service.update_one(
            collection_name='materials',
            query={"_id": ObjectId(material_id)},
            update={"$set": {"stock": new_stock}}
        )
        
        if not result:
            raise HTTPException(status_code=400, detail="Material stock update failed")

        stock_change = {
            "material_id": str(material["_id"]),
            "change_type": stock_update.changeType,
            "quantity": stock_update.quantityChange,
            "price_at_time": current_price,
            "total_value": stock_update.quantityChange * current_price,
            "date": datetime.utcnow()
        }
        await mongodb_service.insert_one(collection_name='stock_changes', document=stock_change)
        
        updated_material = await mongodb_service.find_one(collection_name='materials', query={"_id": ObjectId(material_id)})
        return updated_material
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating material stock: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating material stock: {str(e)}")
