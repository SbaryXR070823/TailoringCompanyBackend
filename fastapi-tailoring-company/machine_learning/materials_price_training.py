import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from datetime import datetime
from typing import List, Dict

async def train_material_price_model(mongodb_service):
    """
    Trains a model to predict next year's price based on historical data and price trends.
    """
    materials_data = await mongodb_service.find_all("materials_price_updates")
    
    df = pd.DataFrame(materials_data)
    
    df['year'] = pd.to_datetime(df['updatedAt']).dt.year
    df['materialId'] = df['materialId'].astype(str)
    
    # Sort by materialId and year
    df = df.sort_values(['materialId', 'year'])
    
    X, y = [], []
    
    for material_id in df['materialId'].unique():
        material_prices = df[df['materialId'] == material_id].sort_values('year')
        
        if len(material_prices) < 2:  
            continue
            
        for i in range(len(material_prices) - 1):
            current_price = material_prices.iloc[i]['price']
            next_price = material_prices.iloc[i + 1]['price']
            
            price_change = next_price - current_price
            price_change_pct = (price_change / current_price) * 100
            
            features = [
                current_price,
                price_change,
                price_change_pct
            ]
            
            if i > 0:
                prev_price = material_prices.iloc[i-1]['price']
                prev_price_change = current_price - prev_price
                prev_price_change_pct = (prev_price_change / prev_price) * 100
                features.extend([prev_price_change, prev_price_change_pct])
            else:
                features.extend([0, 0]) 
                
            X.append(features)
            y.append(next_price)
    
    if len(X) == 0:
        raise ValueError("Not enough historical data for training")
    
    # Convert to numpy arrays
    X = np.array(X)
    y = np.array(y)
    
    model = RandomForestRegressor(
        n_estimators=200,  # More trees
        max_depth=8,       # Deeper trees
        min_samples_split=2,
        random_state=42
    )
    model.fit(X, y)
    
    return model

async def predict_next_year_price(model, mongodb_service, material_id: str) -> float:
    """
    Predicts the next year's price for a specific material using only materialId.
    """
    material_data = await mongodb_service.find_with_conditions(
        collection_name="materials_price_updates",
        conditions={"materialId": material_id}
    )
    
    if not material_data:
        raise ValueError(f"No data found for material ID: {material_id}")
    
    df = pd.DataFrame(material_data)
    df['updatedAt'] = pd.to_datetime(df['updatedAt'])
    df = df.sort_values('updatedAt')
    
    if len(df) < 2:
        raise ValueError("Not enough historical data for prediction")

    latest_price = df.iloc[-1]['price']
    prev_price = df.iloc[-2]['price']
    
    price_change = latest_price - prev_price
    price_change_pct = (price_change / prev_price) * 100
    
    if len(df) >= 3:
        prev_prev_price = df.iloc[-3]['price']
        prev_price_change = prev_price - prev_prev_price
        prev_price_change_pct = (prev_price_change / prev_prev_price) * 100
    else:
        prev_price_change = 0
        prev_price_change_pct = 0
    
    features = [[
        latest_price,
        price_change,
        price_change_pct,
        prev_price_change,
        prev_price_change_pct
    ]]
    
    prediction = model.predict(features)[0]
    
    if price_change > 0:
        prediction = max(prediction, latest_price + (price_change * 0.5))
    
    return float(prediction)