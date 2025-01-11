from datetime import datetime
from typing import List, Tuple
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import OneHotEncoder
from bson import ObjectId
import asyncio

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

def convert_dates(data):
    """
    Convert date fields to datetime with consistent timezone-naive format.
    """
    for field in ["pickup_time", "finished_order_time"]:
        if field in data and isinstance(data[field], str):
            # Convert to datetime and strip timezone information
            data[field] = pd.to_datetime(data[field], errors="coerce")
            if isinstance(data[field], pd.Timestamp):
                data[field] = data[field].tz_localize(None)  # Make timezone-naive for Timestamp
    return data

async def train_workmanship_model(mongodb_service):
    """
    Trains a model to predict workmanship based on order and product data and marks used products in AI.
    """
    orders_data = await mongodb_service.find_all("orders")
    picked_up_orders = [order for order in orders_data if order.get('status') == 'PickedUp']
    products_data = await mongodb_service.find_all("products")
    
    picked_up_orders = [convert_dates(order) for order in picked_up_orders]

    df_orders = pd.DataFrame(picked_up_orders)
    df_products = pd.DataFrame(products_data)

    merged_df = pd.merge(df_orders, df_products, left_on="product_id", right_on="_id", suffixes=("_order", "_product"))

    merged_df['number_of_materials'] = merged_df['materials'].apply(len)
    merged_df['pickup_days'] = (
        (merged_df['pickup_time'] - merged_df['finished_order_time'])
        .dt.days.fillna(0).clip(lower=0)  # Ensure non-negative values
    )
    encoder = OneHotEncoder()
    type_encoded = encoder.fit_transform(merged_df[['type']]).toarray()
    type_encoded_df = pd.DataFrame(type_encoded, columns=encoder.get_feature_names_out(['type']))

    features = pd.concat(
        [
            merged_df[['number_of_materials', 'materials_price', 'time_taken', 'pickup_days']],
            type_encoded_df,
        ],
        axis=1,
    )

    target = merged_df['workmanship'].clip(lower=50) 

    X_train, X_test, y_train, y_test = train_test_split(features, target, test_size=0.2, random_state=42)

    model = RandomForestRegressor(random_state=42)
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    print(predictions)
    mse = mean_squared_error(y_test, predictions)
    print(f"Model Mean Squared Error: {mse}")

    used_product_ids = merged_df['_id_product'].unique()  
    for product_id in used_product_ids:
        product_to_update = await mongodb_service.find_one(collection_name='products', query={"_id": ObjectId(product_id)})
        if product_to_update:
            product_to_update.pop('_id', None) 
            product_to_update['is_used_in_ai'] = True
            await mongodb_service.update_one(
                collection_name='products',
                query={"_id": ObjectId(product_id)},
                update=product_to_update
            )

    return model, encoder

async def predict_workmanship(
    model: RandomForestRegressor,
    encoder: OneHotEncoder,
    product_data: dict[str, any],
    order_data: dict[str, any]
) -> float:
    try:
        features = {
            'number_of_materials': len(product_data.get('materials', [])),
            'materials_price': product_data.get('materials_price', 0),
            'time_taken': order_data.get('time_taken', 0),
        }
        
        order_data = convert_dates(order_data)
        if 'pickup_time' in order_data and 'finished_order_time' in order_data:
            pickup_days = (order_data['pickup_time'] - order_data['finished_order_time']).days
            features['pickup_days'] = max(0, pickup_days)
        else:
            features['pickup_days'] = 0
        
        product_type = product_data.get('type', '')
        categories = encoder.categories_[0]
        
        for category in categories:
            col_name = f"type_{category}"
            features[col_name] = 1.0 if product_type == category else 0.0
        
        features_df = pd.DataFrame([features])
        
        prediction = model.predict(features_df)[0]
        
        return max(50.0, float(prediction))
        
    except Exception as e:
        print(f"Error in predict_workmanship: {str(e)}")
        raise e