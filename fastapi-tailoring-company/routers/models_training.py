from fastapi import APIRouter, HTTPException
from mongo.mongo_service import MongoDBService
from machine_learning.materials_price_training import train_material_price_model
from machine_learning.products_workmanship_tranining import train_workmanship_model
import pickle
import logging
from bson import ObjectId
from bson.binary import Binary
from datetime import date
from sklearn.preprocessing import OneHotEncoder

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
    
@router.post("/start_workmanship_training")
async def start_workmanship_training():
    """
    Endpoint to start training the workmanship prediction model.
    """
    try:
        model, encoder = await train_workmanship_model(mongodb_service)
        model_binary = serialize_model(model, encoder)
        
        existing_latest_model = await mongodb_service.find_with_conditions(
            collection_name="model_storage",
            conditions={"model_name": "workmanship_model", "isLatest": True}
        )

        if existing_latest_model and len(existing_latest_model) > 0:
            logger.info(
                f"Updating existing latest machine learning model for workmanship_model with id: {existing_latest_model[0]['_id']}"
            )
            await mongodb_service.update_one(
                collection_name="model_storage",
                query={"_id": ObjectId(existing_latest_model[0]["_id"])},
                update={"isLatest": False}
            )

        # Save the new model as the latest
        await mongodb_service.insert_one(
            collection_name="model_storage",
            document={
                "model_name": "workmanship_model",
                "model": Binary(model_binary),
                "isLatest": True,
                "createdAt": str(date.today())
            }
        )

        return {"message": "Training completed and workmanship model saved successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")
    


def serialize_model(model, encoder):
    """
    Serialize model and encoder with version compatibility handling
    """
    encoder_data = {
        "categories_": encoder.categories_,
        "dtype": encoder.dtype,
        "handle_unknown": getattr(encoder, "handle_unknown", "error")
    }
    
    if hasattr(encoder, "sparse_output"):
        encoder_data["sparse_output"] = encoder.sparse_output
    else:
        encoder_data["sparse_output"] = getattr(encoder, "sparse", True)
    
    model_data = {
        "model": model,
        "encoder_data": encoder_data
    }
    return pickle.dumps(model_data)

def deserialize_model(stored_data):
    """
    Deserialize model and encoder with version compatibility handling
    """
    model_data = pickle.loads(stored_data)
    model = model_data["model"]
    
    encoder_data = model_data["encoder_data"]
    encoder = OneHotEncoder(
        sparse_output=encoder_data["sparse_output"],
        handle_unknown='ignore', 
        dtype=encoder_data["dtype"]
    )
    encoder.categories_ = encoder_data["categories_"]
    
    return model, encoder