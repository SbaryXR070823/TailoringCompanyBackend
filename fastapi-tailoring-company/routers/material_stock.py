from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from models.material_model import Material
from mongo.mongodb import get_collection
import logging

router = APIRouter(
    prefix="/materials",
    tags=["materials"],
)

class StockUpdate(BaseModel):
    quantityChange: int

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
        
        new_stock = current_stock + stock_update.quantityChange
        
        if new_stock < 0:
            raise HTTPException(status_code=400, detail=f"Insufficient stock. Current: {current_stock}, Requested change: {stock_update.quantityChange}")
        
        result = await collection.update_one(
            {"_id": ObjectId(material_id)},
            {"$set": {"stock": new_stock}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Material stock update failed")
        
        updated_material = await collection.find_one({"_id": ObjectId(material_id)})
        updated_material["_id"] = str(updated_material["_id"])
        return updated_material
        
    except Exception as e:
        logging.error(f"Error updating material stock: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating material stock: {str(e)}")
