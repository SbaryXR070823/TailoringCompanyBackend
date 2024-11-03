from fastapi import APIRouter, HTTPException
from mongo.mongo_service import MongoDBService
from machine_learning.materials_price_training import train_material_price_model
import pickle
import logging
from bson import ObjectId
from bson.binary import Binary
from datetime import date

logger = logging.getLogger(__name__)

router = APIRouter()

connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

@router.post("/start_price_training")
async def start_price_training():
    try:
        model = await train_material_price_model(mongodb_service)

        model_binary = pickle.dumps(model)

        existing_latest_model = await mongodb_service.find_with_conditions(
            collection_name='model_storage',
            conditions={"model_name" : "material_price_model", "isLatest": True}
        )
        
        logger.info(f"Existing ML model found: {existing_latest_model}")
        
        if existing_latest_model and len(existing_latest_model) > 0:
            logger.info(f"Updating existing latest machine learning model for material_price_model with id:{existing_latest_model[0]["_id"]}")
            await mongodb_service.update_one(
                collection_name="model_storage",
                query={"_id": ObjectId(existing_latest_model[0]["_id"])},
                update={"isLatest": False}
            )
            
        
        await mongodb_service.insert_one(
            collection_name='model_storage',
            document={
                "model_name": "material_price_model", 
                "model": Binary(model_binary),
                "isLatest": True,
                "createdAt": str(date.today())
            }
        )

        return {"message": "Training completed and model saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")
    
