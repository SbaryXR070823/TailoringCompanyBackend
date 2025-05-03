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

# Maximum number of files per message
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
    
    # Check if thread exists and user has access
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
        # Check file size
        file_size = 0
        content = await file.read()
        file_size = len(content)
        await file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File {file.filename} exceeds maximum size of 10MB")
        
        # Upload file to GridFS
        storage_id = await gridfs_service.upload_file(file)
        
        # Create file metadata
        file_metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file_size,
            "storage_id": storage_id,
            "uploaded_by": user_id
        }
        
        # Save file metadata to MongoDB
        file_id = await mongodb_service.insert_one(
            collection_name="chat_files",
            document=file_metadata
        )
        
        file_metadata["_id"] = file_id
        uploaded_files.append(file_metadata)
    
    return uploaded_files

@router.get("/files/{file_id}")
async def get_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get file by ID"""
    # Retrieve file metadata
    file_metadata = await mongodb_service.find_by_id(
        collection_name="chat_files",
        id=ObjectId(file_id)
    )
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get the actual file from GridFS
    try:
        file = await gridfs_service.get_file(file_metadata["storage_id"])
        
        # Create a response with the file
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
    # Only admins or file owners can delete files
    user_id = str(current_user["_id"])
    role = current_user.get("role", "user")
    
    # Retrieve file metadata
    file_metadata = await mongodb_service.find_by_id(
        collection_name="chat_files",
        id=ObjectId(file_id)
    )
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if user is authorized to delete the file
    if role != "admin" and file_metadata["uploaded_by"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this file")
    
    # Delete file from GridFS
    success = await gridfs_service.delete_file(file_metadata["storage_id"])
    
    if not success:
        raise HTTPException(status_code=500, detail="Error deleting file from storage")
    
    # Delete file metadata from MongoDB
    deleted_count = await mongodb_service.delete_one(
        collection_name="chat_files",
        query={"_id": ObjectId(file_id)}
    )
    
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="File metadata not found")
    
    return {"message": "File deleted successfully"}
