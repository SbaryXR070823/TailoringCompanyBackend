from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from models.material_model import Material
from mongo.mongodb import get_collection, mongodb_service
from datetime import datetime
import logging

router = APIRouter(
    prefix="/materials",
    tags=["materials"],
)

class StockUpdate(BaseModel):
    quantityChange: int
    changeType: str

@router.patch("/{material_id}/stock", response_model=Material)
async def update_material_stock(
    material_id: str, 
    stock_update: StockUpdate = Body(...),
    collection = Depends(get_collection("materials"))
):
    """
    Update the stock quantity of a material
    
    - **material_id**: ID of the material to update
    - **quantityChange**: Amount to add to the stock (negative to decrease)
    """
    try:
        material = await collection.find_one({"_id": ObjectId(material_id)})
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        
        current_stock = material.get("stock", 0)
        current_price = material.get("price", 0)
        
        new_stock = current_stock + stock_update.quantityChange
        
        if new_stock < 0:
            raise HTTPException(status_code=400, detail=f"Insufficient stock. Current: {current_stock}, Requested change: {stock_update.quantityChange}")
        
        result = await collection.update_one(
            {"_id": ObjectId(material_id)},
            {"$set": {"stock": new_stock}}
        )
        
        if result.modified_count == 0:
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
        
        updated_material = await collection.find_one({"_id": ObjectId(material_id)})
        updated_material["_id"] = str(updated_material["_id"])
        return updated_material
        
    except Exception as e:
        logging.error(f"Error updating material stock: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating material stock: {str(e)}")
