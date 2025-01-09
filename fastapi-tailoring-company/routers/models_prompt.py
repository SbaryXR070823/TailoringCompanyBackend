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

@router.post("/prompt_materials_predictions/{material_id}")
async def load_model_materials_price_predictions(material_id: str):
    stored_model = await mongodb_service.find_one(
        collection_name='model_storage',
        query={"model_name": "material_price_model", "isLatest" : True}
    )
    
    model = pickle.loads(stored_model['model'])
    
    return await predict_next_year_price(model, mongodb_service, material_id)

@router.post("/prompt_workmanship_prediction")
async def predict_product_workmanship(request: dict):
    try:
        # logger.info("Starting workmanship prediction")
        # logger.info(f"Received request: {request}")

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
            # Load model and encoder from pickle
            stored_model_data = pickle.loads(stored_data["model"])
            model = stored_model_data["model"]
            encoder_categories = stored_model_data["encoder_categories"]

            # Recreate the encoder with the saved categories
            encoder = OneHotEncoder()
            encoder.categories_ = encoder_categories
            print(encoder.categories_)
            
            # Convert datetime strings to datetime objects
            pickup_time = datetime.fromisoformat(request['estimated_pickup_time'].replace('Z', '+00:00'))
            finish_time = datetime.fromisoformat(request['estimated_finish_time'].replace('Z', '+00:00'))
            
            # Prepare product and order data for prediction
            product_data = {
                "type": request['product_type'],
                "materials": request['materials'],
                "materials_price": float(request['materials_price'])
            }
            # logger.info(f"Product data prepared: {product_data}")
            
            order_data = {
                "time_taken": float(request['estimated_time_taken']),
                "pickup_time": pickup_time,
                "finished_order_time": finish_time
            }
            # logger.info(f"Order data prepared: {order_data}")
            
            # Get prediction
            prediction = await predict_workmanship(
                model=model,
                encoder=encoder,
                product_data=product_data,
                order_data=order_data
            )
            # logger.info(f"Prediction completed: {prediction}")
            
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