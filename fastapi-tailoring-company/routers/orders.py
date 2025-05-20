from fastapi import APIRouter, HTTPException
from mongo.mongo_service import MongoDBService
from bson import ObjectId
from typing import Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

# Get all orders
@router.get("/orders/")
async def get_orders():
    try:
        orders = await mongodb_service.find_all(collection_name='orders')
        logger.info(f"Retrieved {len(orders)} orders")
        return orders
    except Exception as e:
        logger.error(f"Error retrieving orders: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving orders")

# Create a new order
@router.post("/orders/")
async def create_order(order: dict):
    if '_id' in order:
        del order['_id']

    try:
        order_id = await mongodb_service.insert_one(collection_name='orders', document=order)
        new_order = await mongodb_service.find_one(collection_name='orders', query={"_id": ObjectId(order_id)})
        
        if not new_order:
            raise HTTPException(status_code=500, detail="Error retrieving the created order")

        if "materials" in order:
            for material_use in order["materials"]:
                material_id = material_use.get("materialId")
                quantity_used = material_use.get("quantity", 0)
                
                if material_id and quantity_used > 0:
                    material = await mongodb_service.find_one(
                        collection_name='materials', 
                        query={"_id": ObjectId(material_id)}
                    )
                    if material:
                        stock_change = {
                            "material_id": material_id,
                            "change_type": "OrderUpdate",
                            "quantity": -quantity_used,  # Negative because stock is being used
                            "price_at_time": material.get("price", 0),
                            "total_value": -quantity_used * material.get("price", 0)
                        }
                        await mongodb_service.insert_one(collection_name='stock_changes', document=stock_change)

        logger.info(f"Order created with ID: {order_id}")
        return new_order
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while creating the order")

# Get an order by ID
@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    try:
        order = await mongodb_service.find_one(collection_name='orders', query={"_id": ObjectId(order_id)})
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        logger.info(f"Order retrieved with ID: {order_id}")
        return order
    except Exception as e:
        logger.error(f"Error retrieving order with ID {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving the order")

# Update an order by ID
@router.put("/orders/{order_id}")
async def update_order(order_id: str, order: dict):
    update_data = order
    update_data.pop('_id', None)

    try:
        updated_order = await mongodb_service.update_one(
            collection_name='orders',
            query={"_id": ObjectId(order_id)},
            update=update_data
        )
        if not updated_order:
            raise HTTPException(status_code=404, detail="Order not found")

        logger.info(f"Order updated with ID: {order_id}")
        return updated_order
    except Exception as e:
        logger.error(f"Error updating order with ID {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while updating the order")

# Delete an order by ID
@router.delete("/orders/{order_id}")
async def delete_order(order_id: str):
    try:
        deleted_count = await mongodb_service.delete_one(collection_name='orders', query={"_id": ObjectId(order_id)})
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="Order not found")

        logger.info(f"Order deleted with ID: {order_id}")
        return {"message": "Order deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting order with ID {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while deleting the order")
    
@router.get("/orders/by_user/{userEmail}")
async def get_orders_by_user(userEmail: str):
    try:
        orders = await mongodb_service.find_with_conditions(
            collection_name='orders',
            conditions={"userEmail": userEmail}
        )

        if not orders:
            logger.info(f"No orders found for user ID: {userEmail}")
            raise HTTPException(status_code=404, detail="No orders found for this user")

        logger.info(f"Retrieved {len(orders)} orders for user ID: {userEmail}")
        return orders
    except Exception as e:
        logger.error(f"Error retrieving orders for user ID {userEmail}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving orders for the user")
