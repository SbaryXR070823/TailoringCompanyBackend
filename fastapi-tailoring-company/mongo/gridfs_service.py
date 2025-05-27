import logging
import motor.motor_asyncio
import pymongo
from pymongo import MongoClient
import gridfs
from bson import ObjectId
from fastapi import UploadFile
from gridfs import GridFSBucket
from pymongo.errors import PyMongoError
from PIL import Image, ImageOps
import io

logger = logging.getLogger(__name__)

class GridFSService:
    def __init__(self, connection_string: str, database_name: str = "TailoringDb"):
        self.async_client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
        self.async_db = self.async_client[database_name]
        
        self.client = pymongo.MongoClient(connection_string)
        self.db = self.client[database_name]
        self.fs = GridFSBucket(self.db)        
    async def upload_file(self, file: UploadFile) -> dict:
        """
        Upload a file to GridFS
        For images, also creates and uploads a thumbnail
        Returns a dict with file_id and thumbnail_id (if applicable)
        """
        try:
            logger.info(f"GridFS: Starting upload of file {file.filename}, content_type: {file.content_type}")
            file_data = await file.read()
            logger.info(f"GridFS: Read {len(file_data)} bytes from file")
            
            file_id = self.fs.upload_from_stream(
                filename=file.filename,
                source=file_data,
                metadata={
                    "content_type": file.content_type,
                    "file_type": "original"
                }
            )
            logger.info(f"GridFS: Original file uploaded successfully with ID: {file_id}")
            
            result = {"file_id": str(file_id)}
            
            if file.content_type and file.content_type.startswith('image/'):
                try:
                    thumbnail_data = await self._generate_thumbnail(file_data, file.content_type)
                    if thumbnail_data:
                        thumbnail_filename = f"thumb_{file.filename}"
                        thumbnail_id = self.fs.upload_from_stream(
                            filename=thumbnail_filename,
                            source=thumbnail_data,
                            metadata={
                                "content_type": file.content_type,
                                "file_type": "thumbnail",
                                "original_file_id": str(file_id)
                            }
                        )
                        result["thumbnail_id"] = str(thumbnail_id)
                        logger.info(f"GridFS: Thumbnail uploaded successfully with ID: {thumbnail_id}")
                except Exception as thumb_error:
                    logger.warning(f"Failed to generate thumbnail for {file.filename}: {thumb_error}")
            
            await file.seek(0)  # Reset file pointer
            return result
        except PyMongoError as e:
            logger.error(f"Error uploading file to GridFS: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error uploading file to GridFS: {str(e)}")
            raise

    async def _generate_thumbnail(self, image_data: bytes, content_type: str, max_size: tuple = (300, 200)) -> bytes:
        """Generate a thumbnail from image data"""
        try:
            image = Image.open(io.BytesIO(image_data))
            
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            thumbnail_buffer = io.BytesIO()
            
            image.save(thumbnail_buffer, format='JPEG', quality=85, optimize=True)
            thumbnail_buffer.seek(0)
            
            return thumbnail_buffer.getvalue()
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            return None
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
