from fastapi import APIRouter, HTTPException
from mongo.mongo_service import MongoDBService
import logging
from bson import ObjectId

router = APIRouter()
logger = logging.getLogger(__name__)

connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

@router.get("/products/")
async def get_products():
    try:
        products = await mongodb_service.find_all(collection_name='products')
        logger.info(f"Retrieved {len(products)} products")
        return products
    except Exception as e:
        logger.error(f"Error retrieving products: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving products")

@router.post("/products/")
async def create_product(product: dict):
    if '_id' in product:
        del product['_id']
    
    product_id = await mongodb_service.insert_one(collection_name='products', document=product)
    new_product = await mongodb_service.find_one(collection_name='products', query={"_id": ObjectId(product_id)})

    if not new_product:
        raise HTTPException(status_code=500, detail="Error retrieving the created product")

    return new_product

@router.get("/products/{product_id}")
async def get_product(product_id: str):
    product = await mongodb_service.find_one(collection_name='products', query={"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/products/{product_id}")
async def update_product(product_id: str, product: dict):
    product.pop('_id', None)
    updated_product = await mongodb_service.update_one(
        collection_name='products',
        query={"_id": ObjectId(product_id)},
        update=product
    )
    if not updated_product:
        raise HTTPException(status_code=404, detail="Product not found")
    return updated_product

@router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    deleted_count = await mongodb_service.delete_one(collection_name='products', query={"_id": ObjectId(product_id)})
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}