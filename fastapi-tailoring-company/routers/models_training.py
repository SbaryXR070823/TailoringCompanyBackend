from fastapi import APIRouter, HTTPException
from mongo.mongo_service import MongoDBService
from machine_learning.materials_price_training import train_material_price_model
import pickle
from bson.binary import Binary
from datetime import date

router = APIRouter()

connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

@router.post("/start_price_training")
async def start_price_training():
    try:
        model = await train_material_price_model(mongodb_service)

        model_binary = pickle.dumps(model)

        await mongodb_service.insert_one(
            collection_name='model_storage',
            document={
                "model_name": "material_price_model", 
                "model": Binary(model_binary),
                "createdAt": str(date.today())
            }
        )

        return {"message": "Training completed and model saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")
    
