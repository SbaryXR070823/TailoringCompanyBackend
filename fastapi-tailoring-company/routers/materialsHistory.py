from fastapi import APIRouter, HTTPException
from mongo.mongo_service import MongoDBService
import logging
from bson import ObjectId


router = APIRouter()
logger = logging.getLogger(__name__)

connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

@router.get("/materials_price_updates/")
async def get_materials_price_updates():
    try:
        price_updates = await mongodb_service.find_all(collection_name='materials_price_updates')
        logger.info(f"Retrieved {len(price_updates)} materials price updates")
        return price_updates
    except Exception as e:
        logger.error(f"Error retrieving materials price updates: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving materials price updates")

@router.post("/materials_price_updates/")
async def create_materials_price_update(price_update: dict):    
    material_id = price_update.get('materialId')
    
    logger.info(f"Querying for materialId: {material_id} with isLatest=True")
    
    existing_price_update = await mongodb_service.find_with_conditions(
        collection_name='materials_price_updates', 
        conditions={"materialId": material_id, "isLatest": True}
    )

    logger.info(f"Existing price update found: {existing_price_update}")

    if existing_price_update and len(existing_price_update)> 0:
        logger.info(f"Updating existing latest price update for materialId: {material_id}")
        await mongodb_service.update_one(
            collection_name='materials_price_updates', 
            query={"_id": ObjectId(existing_price_update[0]["_id"])},
            update={"isLatest": False}
        )

    if '_id' in price_update:
        del price_update['_id']
    
    new_id = await mongodb_service.insert_one(collection_name='materials_price_updates', document=price_update)
    
    new_price_update = await mongodb_service.find_one(
        collection_name='materials_price_updates', 
        query={"_id": ObjectId(new_id)}
    )

    if not new_price_update:
        raise HTTPException(status_code=500, detail="Error retrieving the created materials price update")

    return new_price_update


@router.get("/materials_price_updates/{update_id}")
async def get_materials_price_update(update_id: str):
    price_update = await mongodb_service.find_one(collection_name='materials_price_updates', query={"_id": ObjectId(update_id)})
    if not price_update:
        raise HTTPException(status_code=404, detail="Materials price update not found")
    return price_update

@router.put("/materials_price_updates/{update_id}")
async def update_materials_price_update(update_id: str, price_update: dict):
    price_update.pop('_id', None)

    updated_price_update = await mongodb_service.update_one(
        collection_name='materials_price_updates',
        query={"_id": ObjectId(update_id)},
        update=price_update
    )

    if not updated_price_update:
        raise HTTPException(status_code=404, detail="Materials price update not found")
    
    return updated_price_update

@router.delete("/materials_price_updates/{update_id}")
async def delete_materials_price_update(update_id: str):
    deleted_count = await mongodb_service.delete_one(collection_name='materials_price_updates', query={"_id": ObjectId(update_id)})
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Materials price update not found")
    return {"message": "Materials price update deleted successfully"}