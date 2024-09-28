from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from firebase.firebase_config import set_custom_user_claims, get_user_custom_claims, verify_firebase_token

app = FastAPI()

class RoleAssignmentRequest(BaseModel):
    email: str
    role: str

@app.post("/assign-role/")
def assign_role(request: RoleAssignmentRequest):
    try:
        # Call the function to set the user's role
        result = set_custom_user_claims(request.email, request.role)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.get("/user-role/{email}")
def get_user_role(email: str):
    try:
        claims = get_user_custom_claims(email)
        return {"email": email, "role": claims.get("role", "No role assigned")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/secure-endpoint")
def secure_endpoint(token: str):
    decoded_token = verify_firebase_token(token)
    return {"message": "Token is valid", "user_id": decoded_token['uid']}

