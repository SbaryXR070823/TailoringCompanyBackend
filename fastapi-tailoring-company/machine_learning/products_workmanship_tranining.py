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
    # Step 1: Retrieve data from MongoDB
    orders_data = await mongodb_service.find_all("orders")
    picked_up_orders = [order for order in orders_data if order.get('status') == 'PickedUp']
    products_data = await mongodb_service.find_all("products")
    
    # Convert date strings to datetime in orders_data
    picked_up_orders = [convert_dates(order) for order in picked_up_orders]

    # Convert data to pandas DataFrames
    df_orders = pd.DataFrame(picked_up_orders)
    df_products = pd.DataFrame(products_data)

    # Ensure merging and processing
    merged_df = pd.merge(df_orders, df_products, left_on="product_id", right_on="_id", suffixes=("_order", "_product"))

    # Step 2: Prepare features and target
    merged_df['number_of_materials'] = merged_df['materials'].apply(len)
    merged_df['pickup_days'] = (
        (merged_df['pickup_time'] - merged_df['finished_order_time'])
        .dt.days.fillna(0).clip(lower=0)  # Ensure non-negative values
    )
    # Encode `type` using one-hot encoding
    encoder = OneHotEncoder()
    type_encoded = encoder.fit_transform(merged_df[['type']]).toarray()
    type_encoded_df = pd.DataFrame(type_encoded, columns=encoder.get_feature_names_out(['type']))

    # Combine all features
    features = pd.concat(
        [
            merged_df[['number_of_materials', 'materials_price', 'time_taken', 'pickup_days']],
            type_encoded_df,
        ],
        axis=1,
    )

    # Target variable
    target = merged_df['workmanship'].clip(lower=50)  # Minimum value of 50

    # Step 3: Split data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(features, target, test_size=0.2, random_state=42)

    # Step 4: Train the RandomForest model
    model = RandomForestRegressor(random_state=42)
    model.fit(X_train, y_train)

    # Step 5: Evaluate the model
    predictions = model.predict(X_test)
    print(predictions)
    mse = mean_squared_error(y_test, predictions)
    print(f"Model Mean Squared Error: {mse}")

    # Step 6: Mark products as used in AI
    used_product_ids = merged_df['_id_product'].unique()  # Get unique product IDs used in training
    for product_id in used_product_ids:
        product_to_update = await mongodb_service.find_one(collection_name='products', query={"_id": ObjectId(product_id)})
        if product_to_update:
            product_to_update.pop('_id', None)  # Remove '_id' field to avoid MongoDB update issues
            product_to_update['is_used_in_ai'] = True  # Mark as used in AI
            await mongodb_service.update_one(
                collection_name='products',
                query={"_id": ObjectId(product_id)},
                update=product_to_update
            )

    # Return the trained model and the encoder for future predictions
    return model, encoder

async def predict_workmanship(
    model: RandomForestRegressor,
    encoder: OneHotEncoder,
    product_data: dict[str, any],
    order_data: dict[str, any]
) -> float:
    # Prepare features
    features = {
        'number_of_materials': len(product_data.get('materials', [])),
        'materials_price': product_data.get('materials_price', 0),
        'time_taken': order_data.get('time_taken', 0),
    }
    
    # Calculate pickup days if timestamps available
    order_data = convert_dates(order_data)
    if 'pickup_time' in order_data and 'finished_order_time' in order_data:
        pickup_days = (order_data['pickup_time'] - order_data['finished_order_time']).days
        features['pickup_days'] = max(0, pickup_days)
    else:
        features['pickup_days'] = 0
    
    # Encode product type
    print(product_data)
    type_encoded = encoder.transform([[product_data.get('type', '')]])
    type_features = pd.DataFrame(
        type_encoded,
        columns=encoder.get_feature_names_out(['type'])
    )
    
    # Combine all features
    features_df = pd.concat([
        pd.DataFrame([features]),
        type_features
    ], axis=1)
    
    # Make prediction
    prediction = model.predict(features_df)[0]
    
    # Ensure prediction meets minimum quality threshold
    return max(50.0, float(prediction))