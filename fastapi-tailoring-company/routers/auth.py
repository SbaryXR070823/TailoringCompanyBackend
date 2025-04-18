from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from firebase.firebase_config import set_custom_user_claims, get_user_custom_claims, verify_firebase_token
import logging
from mongo.mongo_service import MongoDBService
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter()

# MongoDB connection
connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

class RoleAssignmentRequest(BaseModel):
    email: str
    role: str

class TokenStorage(BaseModel):
    token: str
    firebase_uid: str

@router.post("/assign-role/")
def assign_role(request: RoleAssignmentRequest):
    logger.info(f"Received request: {request}")
    try:
        result = set_custom_user_claims(request.email, request.role)
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/user-role/{email}")
def get_user_role(email: str):
    logger.info(f"Received request: {email}")
    try:
        claims = get_user_custom_claims(email)
        return {"role": claims.get("role", "No role assigned")}
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/secure-endpoint")
def secure_endpoint(token: str):
    decoded_token = verify_firebase_token(token)
    return {"message": "Token is valid", "user_id": decoded_token['uid']}

@router.post("/store-token")
async def store_token(token_data: TokenStorage):
    """Store a user's Firebase token in the database"""
    try:
        # Try to verify the token with Firebase first
        try:
            decoded_token = verify_firebase_token(token_data.token)
            uid = decoded_token['uid']
            
            # Check if the decoded UID matches the provided UID
            if uid != token_data.firebase_uid:
                raise HTTPException(status_code=400, detail="Token UID doesn't match provided UID")
        except Exception as e:
            logger.warning(f"Firebase verification failed, proceeding with direct token storage: {str(e)}")
        
        # Check if token already exists for this user
        existing_token = await mongodb_service.find_one(
            collection_name="auth_tokens",
            query={"firebase_uid": token_data.firebase_uid}
        )
        
        # Set expiration 24 hours from now
        expiration = datetime.utcnow() + timedelta(hours=24)
        
        if existing_token:
            # Update existing token
            await mongodb_service.update_one(
                collection_name="auth_tokens",
                query={"firebase_uid": token_data.firebase_uid},
                update={
                    "token": token_data.token,
                    "updated_at": datetime.utcnow(),
                    "expires_at": expiration
                }
            )
        else:
            # Create new token entry
            await mongodb_service.insert_one(
                collection_name="auth_tokens",
                document={
                    "firebase_uid": token_data.firebase_uid,
                    "token": token_data.token,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "expires_at": expiration
                }
            )
        
        return {"message": "Token stored successfully"}
    except Exception as e:
        logger.error(f"Error storing token: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to store token: {str(e)}")

@router.post("/sync-user-info")
async def sync_user_info(user_data: dict):
    """
    Endpoint to sync user information from the frontend to ensure database has correct user details
    """
    logger.info(f"Received user info sync request: {user_data}")
    
    # Check if we have the required fields
    if not user_data.get("firebase_uid"):
        raise HTTPException(status_code=400, detail="Missing required field: firebase_uid")
        
    # Check if user exists
    existing_user = await mongodb_service.find_one(
        collection_name="users",
        query={"firebase_uid": user_data["firebase_uid"]}
    )
    
    if existing_user:
        # Update existing user
        logger.info(f"Updating existing user: {user_data['firebase_uid']}")
        
        # Create update object with only fields that have values
        update_data = {}
        if user_data.get("email"):
            update_data["email"] = user_data["email"]
        if user_data.get("name"):
            update_data["name"] = user_data["name"]
        if user_data.get("role"):
            update_data["role"] = user_data["role"]
            
        if update_data:
            await mongodb_service.update_one(
                collection_name="users",
                query={"firebase_uid": user_data["firebase_uid"]},
                update=update_data
            )
        return {"status": "User updated successfully"}
    else:
        # Create new user
        logger.info(f"Creating new user from sync: {user_data['firebase_uid']}")
        new_user = {
            "firebase_uid": user_data["firebase_uid"],
            "email": user_data.get("email", "unknown@example.com"),
            "name": user_data.get("name", "Anonymous User"),
            "role": user_data.get("role", "user"),
            "created_at": datetime.utcnow()
        }
        
        user_id = await mongodb_service.insert_one("users", new_user)
        return {"status": "User created successfully", "user_id": str(user_id)}
