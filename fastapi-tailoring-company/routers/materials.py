from fastapi import APIRouter, HTTPException
from mongo.mongo_service import MongoDBService
import logging
from bson import ObjectId

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
