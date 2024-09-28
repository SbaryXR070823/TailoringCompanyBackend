from fastapi import HTTPException
import firebase_admin
from firebase_admin import credentials, auth

cred = credentials.Certificate("C:\\Alex\\FIreBaseSecret\\serviceAccountKey.json")
firebase_admin.initialize_app(cred)

def set_custom_user_claims(email: str, role: str):
    user = auth.get_user_by_email(email)
    
    auth.set_custom_user_claims(user.uid, {"role": role})

    return {"message": f"Success! {role} role assigned to {email}"}

def get_user_custom_claims(email: str):
    user = auth.get_user_by_email(email)
    return user.custom_claims

def verify_firebase_token(token: str):
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

