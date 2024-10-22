from fastapi import APIRouter, HTTPException
from mongo.mongo_service import MongoDBService
from machine_learning.materials_price_training import predict_next_year_price
import pickle
from bson.binary import Binary
from datetime import date

router = APIRouter()

connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

@router.post("/prompt_materials_predictions/{material_id}")
async def load_model_materials_price_predictions(material_id: str):
    stored_model = await mongodb_service.find_one(
        collection_name='model_storage',
        query={"model_name": "material_price_model"}
    )
    
    model = pickle.loads(stored_model['model'])
    
    return await predict_next_year_price(model, mongodb_service, material_id)