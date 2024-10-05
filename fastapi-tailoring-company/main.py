from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from firebase.firebase_config import set_custom_user_claims, get_user_custom_claims, verify_firebase_token
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
origins = [
    "http://localhost:4200",  # Angular app
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

class RoleAssignmentRequest(BaseModel):
    email: str
    role: str

@app.post("/assign-role/")
def assign_role(request: RoleAssignmentRequest):
    logger.info(f"Received request: {request}")
    try:
        result = set_custom_user_claims(request.email, request.role)
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
@app.get("/user-role/{email}")
def get_user_role(email: str):
    logger.info(f"Received request: {email}")
    try:
        claims = get_user_custom_claims(email)
        return {"email": email, "role": claims.get("role", "No role assigned")}
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/secure-endpoint")
def secure_endpoint(token: str):
    decoded_token = verify_firebase_token(token)
    return {"message": "Token is valid", "user_id": decoded_token['uid']}
