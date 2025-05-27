from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from firebase.firebase_config import verify_token_from_db
from routers.chat import get_current_user
from mongo.mongo_service import MongoDBService
import logging
import json
import io
import base64
from typing import Any, Dict
from datetime import datetime
from bson import ObjectId
import bson

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Database"], prefix="/api/database")

connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle MongoDB-specific data types"""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return {
                "__type": "bytes",
                "__data": base64.b64encode(obj).decode('utf-8')
            }
        if isinstance(obj, bson.Binary):
            return {
                "__type": "bson.Binary",
                "__data": base64.b64encode(obj).decode('utf-8'),
                "__subtype": obj.subtype
            }
        return super().default(obj)

def decode_special_types(obj):
    """Recursively decode special types that were encoded during export"""
    if isinstance(obj, dict):
        if obj.get("__type") == "bytes":
            return base64.b64decode(obj["__data"])
        elif obj.get("__type") == "bson.Binary":
            data = base64.b64decode(obj["__data"])
            subtype = obj.get("__subtype", 0)
            return bson.Binary(data, subtype)
        else:
            return {key: decode_special_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [decode_special_types(item) for item in obj]
    else:
        return obj

def check_admin_access(current_user: dict) -> bool:
    """Check if the current user has admin access"""
    user_role = current_user.get("role")
    user_email = current_user.get("email")
    logger.info(f"Checking admin access for user {user_email} with role: {user_role}")
    is_admin = user_role == "admin"
    logger.info(f"Admin access check result: {is_admin}")
    return is_admin

@router.get("/export")
async def export_database(current_user: dict = Depends(get_current_user)):
    """
    Export the entire database as a JSON file.
    Only available to admin users.
    """
    if not check_admin_access(current_user):
        raise HTTPException(status_code=403, detail="Only administrators can export the database")
    
    try:
        logger.info(f"Starting database export by user: {current_user.get('email')}")
        
        collection_names = await mongodb_service.db.list_collection_names()
        
        database_data = {
            "export_metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "exported_by": current_user.get("email"),
                "collections_count": len(collection_names),
                "database_name": mongodb_service.db.name
            },
            "collections": {}
        }
        
        total_documents = 0
        
        for collection_name in collection_names:
            logger.info(f"Exporting collection: {collection_name}")
            
            documents = await mongodb_service.find_all(collection_name)
            database_data["collections"][collection_name] = documents
            total_documents += len(documents)
            
            logger.info(f"Exported {len(documents)} documents from {collection_name}")
        
        database_data["export_metadata"]["total_documents"] = total_documents
        
        json_str = json.dumps(database_data, cls=JSONEncoder, indent=2)
        
        json_bytes = json_str.encode('utf-8')
        file_like = io.BytesIO(json_bytes)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"database_backup_{timestamp}.json"
        
        logger.info(f"Database export completed. Total collections: {len(collection_names)}, Total documents: {total_documents}")
        
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error during database export: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export database: {str(e)}")

@router.post("/import")
async def import_database(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Import database from a JSON file.
    This will replace the entire current database.
    Only available to admin users.
    """
    logger.info(f"Database import requested by user: {current_user.get('email')} with role: {current_user.get('role')}")
    if not check_admin_access(current_user):
        raise HTTPException(status_code=403, detail="Only administrators can import the database")
    
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Only JSON files are supported for database import")
    
    try:
        logger.info(f"Starting database import by user: {current_user.get('email')}")
        
        content = await file.read()
        
        try:
            database_data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
        
        if "collections" not in database_data:
            raise HTTPException(status_code=400, detail="Invalid database backup format: missing 'collections' key")
        
        collections_data = database_data["collections"]
        
        if not isinstance(collections_data, dict):
            raise HTTPException(status_code=400, detail="Invalid database backup format: 'collections' must be an object")
        
        if "export_metadata" in database_data:
            metadata = database_data["export_metadata"]
            logger.info(f"Importing database backup from {metadata.get('timestamp')} by {metadata.get('exported_by')}")
        
        logger.warning("Clearing existing database collections...")
        existing_collections = await mongodb_service.db.list_collection_names()
        
        for collection_name in existing_collections:
            logger.info(f"Dropping collection: {collection_name}")
            await mongodb_service.db[collection_name].drop()
        
        total_imported = 0
        
        for collection_name, documents in collections_data.items():
            if not isinstance(documents, list):
                logger.warning(f"Skipping collection {collection_name}: expected list of documents")
                continue
            
            if not documents:  
                logger.info(f"Skipping empty collection: {collection_name}")
                continue
            
            logger.info(f"Importing {len(documents)} documents into collection: {collection_name}")
            processed_docs = []
            for doc in documents:
                if isinstance(doc, dict):
                    doc = decode_special_types(doc)
                    
                    if "_id" in doc and isinstance(doc["_id"], str):
                        try:
                            doc["_id"] = ObjectId(doc["_id"])
                        except bson.errors.InvalidId:
                            doc.pop("_id", None)
                    
                    for key, value in doc.items():
                        if isinstance(value, str) and (key.endswith(('_at', 'At')) or key in ['timestamp', 'date']):
                            try:
                                doc[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            except (ValueError, AttributeError):
                                pass 
                    
                    processed_docs.append(doc)
            
            if processed_docs:
                await mongodb_service.db[collection_name].insert_many(processed_docs)
                total_imported += len(processed_docs)
                logger.info(f"Successfully imported {len(processed_docs)} documents into {collection_name}")
        
        logger.info(f"Database import completed successfully. Total documents imported: {total_imported}")
        
        return {
            "message": "Database imported successfully",
            "collections_imported": len([c for c, docs in collections_data.items() if docs]),
            "total_documents_imported": total_imported,
            "imported_by": current_user.get("email"),
            "import_timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during database import: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import database: {str(e)}")

@router.get("/collections")
async def get_collections_info(current_user: dict = Depends(get_current_user)):
    """
    Get information about all collections in the database.
    Only available to admin users.
    """
    if not check_admin_access(current_user):
        raise HTTPException(status_code=403, detail="Only administrators can view database information")
    
    try:
        logger.info(f"Getting database collections info for user: {current_user.get('email')}")
        
        collection_names = await mongodb_service.db.list_collection_names()
        
        collections_info = []
        total_documents = 0
        
        for collection_name in collection_names:
            count = await mongodb_service.db[collection_name].estimated_document_count()
            collections_info.append({
                "name": collection_name,
                "document_count": count
            })
            total_documents += count
        
        return {
            "database_name": mongodb_service.db.name,
            "total_collections": len(collection_names),
            "total_documents": total_documents,
            "collections": collections_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting collections info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get database information: {str(e)}")
