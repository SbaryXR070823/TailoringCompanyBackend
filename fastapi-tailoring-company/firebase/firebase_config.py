from fastapi import HTTPException
import firebase_admin
from firebase_admin import credentials, auth
from mongo.mongo_service import MongoDBService
from datetime import datetime

cred = credentials.Certificate("C:\\Alex\\FIreBaseSecret\\serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# MongoDB connection
connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

def set_custom_user_claims(email: str, role: str):
    user = auth.get_user_by_email(email)
    
    auth.set_custom_user_claims(user.uid, {"role": role})

    return {"message": f"Success! {role} role assigned to {email}"}

def get_user_custom_claims(email: str):
    user = auth.get_user_by_email(email)
    return user.custom_claims

def verify_firebase_token(token: str):
    try:
        print(f"Attempting to verify Firebase token, length: {len(token)}")
        decoded_token = auth.verify_id_token(token)
        print(f"Token verification successful for UID: {decoded_token.get('uid')}")
        return decoded_token
    except Exception as e:
        print(f"Firebase token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

async def verify_token_from_db(token: str):
    """Verify a token by checking if it exists in the database"""
    try:
        print(f"Attempting to verify token from database, first 20 chars: {token[:20]}...")
        
        # Find the token in the database
        print("Querying database for token")
        token_entry = await mongodb_service.find_one(
            collection_name="auth_tokens",
            query={"token": token}
        )
        
        if not token_entry:
            print("Token not found in database. Attempting partial match search...")
            
            # Try to find all tokens and compare
            all_tokens = await mongodb_service.find_all(collection_name="auth_tokens")
            print(f"Found {len(all_tokens)} tokens in database")
            
            for entry in all_tokens:
                stored_token = entry.get("token", "")
                
                # Print first 20 chars of stored token for comparison
                if stored_token:
                    print(f"Stored token first 20 chars: {stored_token[:20]}...")
                    
                    # Try trimming whitespace and compare
                    if token.strip() == stored_token.strip():
                        print("Found matching token after trimming whitespace")
                        token_entry = entry
                        break
            
            if not token_entry:
                print("Still no matching token found")
                raise HTTPException(status_code=401, detail="Invalid token - not found in database")
        else:
            print(f"Token found in database for uid: {token_entry.get('firebase_uid')}")
        
        # Check if token is expired
        if token_entry.get("expires_at") and token_entry["expires_at"] < datetime.utcnow():
            print("Token is expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        
        print(f"Token verification successful for UID: {token_entry.get('firebase_uid')}")
        
        # Return a dict similar to what Firebase would return
        return {
            "uid": token_entry["firebase_uid"],
            "token_id": token,
            "auth_time": token_entry.get("updated_at", datetime.utcnow())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

