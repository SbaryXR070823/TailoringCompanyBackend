import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from fastapi.responses import StreamingResponse
from bson import ObjectId
from models.file_models import ChatFile
from mongo.mongo_service import MongoDBService
from mongo.gridfs_service import GridFSService
from firebase.firebase_config import verify_firebase_token, verify_token_from_db
from routers.chat import get_current_user
import io

logger = logging.getLogger(__name__)
router = APIRouter()

# MongoDB connection
connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)
gridfs_service = GridFSService(connection_string=connection_string)

MAX_FILES_PER_MESSAGE = 10
# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

@router.post("/files/upload", response_model=List[dict])
async def upload_files(
    thread_id: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload multiple files for a chat thread"""
    if len(files) > MAX_FILES_PER_MESSAGE:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES_PER_MESSAGE} files can be uploaded per message")
    
    user_id = str(current_user["_id"])
    
    thread = await mongodb_service.find_by_id(
        collection_name="chat_threads",
        id=ObjectId(thread_id)
    )
    
    if not thread:
        raise HTTPException(status_code=404, detail="Chat thread not found")
    
    role = current_user.get("role", "user")
    if role != "admin" and thread["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this chat thread")
    
    uploaded_files = []
    for file in files:
        file_size = 0
        content = await file.read()
        file_size = len(content)
        await file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File {file.filename} exceeds maximum size of 10MB")
        
        # Upload file (and thumbnail if it's an image)
        upload_result = await gridfs_service.upload_file(file)
        
        file_metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file_size,
            "storage_id": upload_result["file_id"],
            "thumbnail_id": upload_result.get("thumbnail_id"),  # May be None for non-images
            "uploaded_by": user_id
        }
        
        file_id = await mongodb_service.insert_one(
            collection_name="chat_files",
            document=file_metadata
        )
        
        # Return the complete file info with both _id and storage_id
        uploaded_files.append({
            "_id": file_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file_size,
            "storage_id": upload_result["file_id"],
            "thumbnail_id": upload_result.get("thumbnail_id"),
            "uploaded_by": user_id
        })
    
    return uploaded_files

@router.get("/files/{file_id}")
async def get_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get file by ID"""
    file_metadata = await mongodb_service.find_by_id(
        collection_name="chat_files",
        id=ObjectId(file_id)
    )
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        file = await gridfs_service.get_file(file_metadata["storage_id"])
        
        return StreamingResponse(
            io.BytesIO(file["data"]), 
            media_type=file["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename=\"{file['filename']}\""
            }
        )
    except Exception as e:
        logger.error(f"Error retrieving file: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving file")

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete file by ID"""
    user_id = str(current_user["_id"])
    role = current_user.get("role", "user")
    
    file_metadata = await mongodb_service.find_by_id(
        collection_name="chat_files",
        id=ObjectId(file_id)
    )
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    if role != "admin" and file_metadata["uploaded_by"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this file")
    
    success = await gridfs_service.delete_file(file_metadata["storage_id"])
    
    if not success:
        raise HTTPException(status_code=500, detail="Error deleting file from storage")
    
    deleted_count = await mongodb_service.delete_one(
        collection_name="chat_files",
        query={"_id": ObjectId(file_id)}
    )
    
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="File metadata not found")
    
    return {"message": "File deleted successfully"}

@router.get("/files/{file_id}/metadata")
async def get_file_metadata(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get file metadata by ID"""
    try:
        file_metadata = await mongodb_service.find_by_id(
            collection_name="chat_files",
            id=ObjectId(file_id)
        )
        
        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Convert ObjectId to string for JSON serialization
        file_metadata["_id"] = str(file_metadata["_id"])
        if "storage_id" in file_metadata:
            file_metadata["storage_id"] = str(file_metadata["storage_id"])
        
        return file_metadata
    except Exception as e:
        logger.error(f"Error getting file metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting file metadata: {str(e)}")

@router.get("/files/{file_id}/thumbnail")
async def get_file_thumbnail(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get thumbnail for an image file by ID"""
    file_metadata = await mongodb_service.find_by_id(
        collection_name="chat_files",
        id=ObjectId(file_id)
    )
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    thumbnail_id = file_metadata.get("thumbnail_id")
    if not thumbnail_id:
        # If no thumbnail, return the original file (for non-images or fallback)
        return await get_file(file_id, current_user)
    
    try:
        file = await gridfs_service.get_file(thumbnail_id)
        
        return StreamingResponse(
            io.BytesIO(file["data"]), 
            media_type=file["content_type"],
            headers={
                "Content-Disposition": f"inline; filename=\"thumb_{file['filename']}\""
            }
        )
    except Exception as e:
        logger.error(f"Error retrieving thumbnail: {e}")
        return await get_file(file_id, current_user)
