from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from firebase.firebase_config import verify_token_from_db
from routers.chat import get_current_user
from mongo.mongo_service import MongoDBService
from mongo.gridfs_service import GridFSService
from fastapi.responses import StreamingResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Carousel"], prefix="/api")

connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)
gridfs_service = GridFSService(connection_string=connection_string)

@router.get("/carousel-images", response_model=List[dict])
async def get_carousel_images():
    """Get all carousel images"""
    try:
        logger.info("Retrieving all carousel images")
        images = await mongodb_service.find_all_sorted(
            collection_name="carousel_images",
            sort=[("createdAt", -1)]
        )
        
        logger.info(f"Found {len(images)} carousel images")
        
        for image in images:
            image["_id"] = str(image["_id"])
            if "createdBy" in image and isinstance(image["createdBy"], ObjectId):
                image["createdBy"] = str(image["createdBy"])
            
            if "url" in image and not image["url"].startswith("http"):
                if not image["url"].startswith("/api/"):
                    image["url"] = f"/api{image['url']}" if image["url"].startswith("/") else f"/api/{image['url']}"
                
        return images
    except Exception as e:
        logger.error(f"Error getting carousel images: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving carousel images")

@router.post("/carousel-images/upload", response_model=dict)
async def upload_carousel_image(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """Upload a new carousel image (admin only)"""
    logger.info(f"Received upload request with file: {file.filename}, name: {name}, description: {description}")
    logger.info(f"Current user: {current_user}")
    
    if not current_user:
        logger.warning("Authentication failed - no user information")
        raise HTTPException(status_code=401, detail="Authentication required")
        
    if current_user.get("role") != "admin":
        logger.warning(f"User {current_user.get('email')} with role {current_user.get('role')} attempted to upload image but is not an admin")
        raise HTTPException(status_code=403, detail="Only administrators can upload carousel images")    
    try:
        logger.info(f"Uploading file {file.filename} to GridFS")
        upload_result = await gridfs_service.upload_file(file, generate_thumbnail=False)
        if isinstance(upload_result, dict):
            file_id = upload_result["file_id"]
        else:
            file_id = upload_result
        
        carousel_image = {
            "name": name,
            "description": description,
            "fileId": file_id,
            "url": f"/api/carousel-images/file/{file_id}",
            "createdAt": datetime.now(),
            "createdBy": str(current_user.get("_id"))
        }
        logger.info("Saving carousel image to MongoDB")
        inserted_id = await mongodb_service.insert_one(
            collection_name="carousel_images",
            document=carousel_image
        )
        
        carousel_image["_id"] = inserted_id
        logger.info(f"Carousel image created with ID: {inserted_id}")
        return carousel_image
    except Exception as e:
        logger.error(f"Error uploading carousel image: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading carousel image: {str(e)}")

@router.get("/carousel-images/file/{file_id}")
async def get_carousel_image_file(file_id: str):
    """Get carousel image file"""
    try:
        logger.info(f"Retrieving file with ID: {file_id}")
        file_data = await gridfs_service.get_file(file_id)
        
        if not file_data:
            logger.warning(f"File with ID {file_id} not found")
            raise HTTPException(status_code=404, detail="Image not found")
            
        logger.info(f"Returning file {file_id} with content type: {file_data['content_type']}")
        
        return StreamingResponse(
            content=iter([file_data["data"]]),
            media_type=file_data["content_type"]
        )
    except Exception as e:
        logger.error(f"Error retrieving carousel image file: {e}")
        raise HTTPException(status_code=404, detail="Image not found")

@router.delete("/carousel-images/{image_id}")
async def delete_carousel_image(
    image_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a carousel image (admin only)"""
    if not current_user:
        logger.warning("Authentication failed - no user information")
        raise HTTPException(status_code=401, detail="Authentication required")
        
    if current_user.get("role") != "admin":
        logger.warning(f"User {current_user.get('email')} with role {current_user.get('role')} attempted to delete image but is not an admin")
        raise HTTPException(status_code=403, detail="Only administrators can delete carousel images")
    
    try:
        logger.info(f"Attempting to delete carousel image with ID: {image_id}")
        
        image = await mongodb_service.find_by_id(
            collection_name="carousel_images",
            id=ObjectId(image_id)
        )
        if not image:
            logger.warning(f"Image with ID {image_id} not found")
            raise HTTPException(status_code=404, detail="Carousel image not found")
        
        file_id = image.get("fileId")
        
        if file_id:
            logger.info(f"Deleting file {file_id} from GridFS")
            await gridfs_service.delete_file(file_id)
        
        logger.info(f"Deleting image record {image_id} from MongoDB")
        result = await mongodb_service.delete_by_id(
            collection_name="carousel_images",
            id=ObjectId(image_id)
        )
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Carousel image not found")
        
        return {"message": "Carousel image deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting carousel image: {e}")
        raise HTTPException(status_code=500, detail="Error deleting carousel image")