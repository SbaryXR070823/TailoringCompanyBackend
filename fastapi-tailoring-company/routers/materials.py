from fastapi import APIRouter, HTTPException
from mongo.mongo_service import MongoDBService
from bson import ObjectId
router = APIRouter()

# Create an instance of the MongoDBService with the same connection string
connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

@router.get("/materials/")
async def get_materials():
    materials = await mongodb_service.find_all(collection_name='materials')
    return materials

@router.post("/materials/")
async def create_material(material: dict):
    material_id = await mongodb_service.insert_one(collection_name='materials', document=material)
    return {"id": material_id}

@router.get("/materials/{material_id}")
async def get_material(material_id: str):
    material = await mongodb_service.find_one(collection_name='materials', query={"_id": ObjectId(material_id)})
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material

@router.put("/materials/{material_id}")
async def update_material(material_id: str, material: dict):
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
