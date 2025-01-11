from fastapi import APIRouter, HTTPException
from mongo.mongo_service import MongoDBService
from machine_learning.materials_price_training import predict_next_year_price
from machine_learning.products_workmanship_tranining import predict_workmanship
import pickle
from sklearn.preprocessing import OneHotEncoder
import logging
from bson.binary import Binary
from datetime import datetime

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

def serialize_model(model, encoder):
    """
    Serialize model and encoder with version compatibility handling
    """
    # Store only the essential encoder attributes
    encoder_data = {
        "categories_": encoder.categories_,
        "dtype": encoder.dtype,
        "handle_unknown": getattr(encoder, "handle_unknown", "error")
    }
    
    # Handle sparse vs sparse_output attribute
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
    
    # Recreate encoder with minimal attributes
    encoder_data = model_data["encoder_data"]
    encoder = OneHotEncoder(
        sparse_output=encoder_data["sparse_output"],
        handle_unknown='ignore',  # Added for robustness
        dtype=encoder_data["dtype"]
    )
    encoder.categories_ = encoder_data["categories_"]
    
    return model, encoder

@router.post("/prompt_workmanship_prediction")
async def predict_product_workmanship(request: dict):
    try:
        # Retrieve latest model and encoder
        stored_data = await mongodb_service.find_one(
            collection_name='model_storage',
            query={"model_name": "workmanship_model", "isLatest": True}
        )
    
        if not stored_data:
            raise HTTPException(status_code=404, detail="Workmanship model not found")

        if 'model' not in stored_data:
            raise HTTPException(status_code=500, detail="Invalid model storage: model data is missing")

        try:
            # Load model and encoder using the new deserialization function
            model, encoder = deserialize_model(stored_data["model"])
            
            # Convert datetime strings to datetime objects
            pickup_time = datetime.fromisoformat(request['estimated_pickup_time'].replace('Z', '+00:00'))
            finish_time = datetime.fromisoformat(request['estimated_finish_time'].replace('Z', '+00:00'))
            
            # Prepare product and order data for prediction
            product_data = {
                "type": request['product_type'],
                "materials": request['materials'],
                "materials_price": float(request['materials_price'])
            }
            
            order_data = {
                "time_taken": float(request['estimated_time_taken']),
                "pickup_time": pickup_time,
                "finished_order_time": finish_time
            }
            
            # Get prediction
            prediction = await predict_workmanship(
                model=model,
                encoder=encoder,
                product_data=product_data,
                order_data=order_data
            )
            
            return {
                "predicted_workmanship": round(prediction, 2),
                "confidence_level": "high" if prediction >= 80 else "medium" if prediction >= 65 else "low"
            }
            
        except KeyError as ke:
            logger.error(f"Missing required field: {str(ke)}")
            raise HTTPException(status_code=400, detail=f"Missing required field: {str(ke)}")
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))