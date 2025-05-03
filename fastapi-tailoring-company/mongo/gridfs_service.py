import logging
import motor.motor_asyncio
import pymongo
from pymongo import MongoClient
import gridfs
from bson import ObjectId
from fastapi import UploadFile
from gridfs import GridFSBucket
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

class GridFSService:
    def __init__(self, connection_string: str, database_name: str = "TailoringDb"):
        self.async_client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
        self.async_db = self.async_client[database_name]
        
        self.client = pymongo.MongoClient(connection_string)
        self.db = self.client[database_name]
        self.fs = GridFSBucket(self.db)
    async def upload_file(self, file: UploadFile) -> str:
        """
        Upload a file to GridFS
        Returns the file_id as a string
        """
        try:
            file_data = await file.read()
            file_id = self.fs.upload_from_stream(
                filename=file.filename,
                source=file_data,
                metadata={
                    "content_type": file.content_type
                }
            )
            await file.seek(0)  # Reset file pointer
            return str(file_id)
        except PyMongoError as e:
            logger.error(f"Error uploading file to GridFS: {e}")
            raise
    async def get_file(self, file_id: str):
        """
        Retrieve a file from GridFS by its ID
        Returns the file data and metadata
        """
        try:
            grid_out = self.fs.open_download_stream(ObjectId(file_id))
            file_data = grid_out.read()
            return {
                "data": file_data,
                "filename": grid_out.filename,
                "content_type": grid_out.metadata.get("content_type", "application/octet-stream"),
                "length": grid_out.length
            }
        except PyMongoError as e:
            logger.error(f"Error retrieving file from GridFS: {e}")
            raise
    async def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from GridFS by its ID
        Returns True if successful
        """
        try:
            self.fs.delete(ObjectId(file_id))
            return True
        except PyMongoError as e:
            logger.error(f"Error deleting file from GridFS: {e}")
            return False
