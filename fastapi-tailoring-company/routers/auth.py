from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from firebase.firebase_config import set_custom_user_claims, get_user_custom_claims, verify_firebase_token
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class RoleAssignmentRequest(BaseModel):
    email: str
    role: str

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
