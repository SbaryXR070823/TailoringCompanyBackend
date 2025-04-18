from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query, Header
from typing import List, Dict, Optional
from bson import ObjectId
from datetime import datetime
import logging
import json
from mongo.mongo_service import MongoDBService
from models.chat_models import ChatThread, Message
from firebase.firebase_config import verify_firebase_token, verify_token_from_db

logger = logging.getLogger(__name__)
router = APIRouter()

connection_string = "mongodb://localhost:27017/TailoringDb"
mongodb_service = MongoDBService(connection_string=connection_string)

async def get_current_user(authorization: str = Header(...)):
    try:
        logger.info(f"Authorization header: {authorization}")
        token = authorization.split("Bearer ")[1]
        logger.info(f"Token: {token[:20]}...") 
        
        try:
            decoded_token = await verify_token_from_db(token)
            logger.info(f"Token verified from database for UID: {decoded_token['uid']}")
        except Exception as db_error:
            logger.warning(f"Database token verification failed: {str(db_error)}, trying Firebase")
            decoded_token = verify_firebase_token(token)
            logger.info(f"Token verified from Firebase for UID: {decoded_token['uid']}")
        user = await mongodb_service.find_one(
            collection_name="users",
            query={"firebase_uid": decoded_token['uid']}
        )
        if not user:
            logger.info(f"User not found in database, creating user object from Firebase token and inserting into DB")
            email = decoded_token.get('email')
            name = decoded_token.get('name')
            
            if email and not name:
                name = email.split('@')[0].title() 
                
            user = {
                "firebase_uid": decoded_token['uid'],
                "email": email if email else "unknown@example.com",
                "role": decoded_token.get('role', 'user'),
                "name": name if name else (email if email else "Anonymous User"),
                "created_at": datetime.utcnow()
            }
            logger.info(f"Creating new user with data: {user}")
            user_id = await mongodb_service.insert_one("users", user)
            user["_id"] = user_id
        return user
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.admin_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str, is_admin: bool = False):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        
        if is_admin:
            self.admin_connections[user_id] = websocket
            
        logger.info(f"User {user_id} {'(admin)' if is_admin else ''} connected to chat WebSocket")
        
    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected from chat WebSocket")
            
        if user_id in self.admin_connections:
            del self.admin_connections[user_id]
            logger.info(f"Admin {user_id} removed from admin connections")
    
    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(json.dumps(message))
            logger.info(f"Message sent to user {user_id}")
            return True
        logger.info(f"User {user_id} not connected, message not sent")
        return False
    
    async def broadcast_to_admins(self, message: dict):
        """Send a message to all connected admin users"""
        sent_count = 0
        
        for admin_id, websocket in self.admin_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
                sent_count += 1
                logger.info(f"Message broadcasted to admin {admin_id}")
            except Exception as e:
                logger.error(f"Error sending message to admin {admin_id}: {str(e)}")
                
        return sent_count > 0

manager = ConnectionManager()

@router.get("/chat/threads", response_model=List[dict])
async def get_user_chat_threads(current_user: dict = Depends(get_current_user)):
    """Get all chat threads for a user or all threads for admins"""
    user_id = str(current_user["_id"])
    role = current_user.get("role", "user")
    
    logger.info(f"User {user_id} with role {role} requesting chat threads")
    
    if role == "admin":
        logger.info("Admin user requesting all threads")
        threads = await mongodb_service.find_all(collection_name="chat_threads")
        logger.info(f"Found {len(threads)} total threads")
    else:
        logger.info(f"Regular user requesting own threads with id {user_id}")
        threads = await mongodb_service.find_with_conditions(
            collection_name="chat_threads",
            conditions={"user_id": user_id}
        )
        logger.info(f"Found {len(threads)} threads for user")
    
    return threads

@router.get("/chat/thread/{thread_id}", response_model=dict)
async def get_chat_thread(
    thread_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific chat thread by ID"""
    user_id = str(current_user["_id"])
    role = current_user.get("role", "user")
    
    thread = await mongodb_service.find_by_id(
        collection_name="chat_threads",
        id=ObjectId(thread_id)
    )
    
    if not thread:
        raise HTTPException(status_code=404, detail="Chat thread not found")
    
    if role != "admin" and thread["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this chat thread")
    
    messages = thread.get("messages", [])
    updated_messages = []
    
    needs_update = False
    for message in messages:
        if not message.get("is_read", False) and message.get("sender_id") != user_id:
            message["is_read"] = True
            needs_update = True
        updated_messages.append(message)
    
    if needs_update:
        thread["messages"] = updated_messages
        await mongodb_service.update_one(
            collection_name="chat_threads",
            query={"_id": ObjectId(thread_id)},
            update={"messages": updated_messages}
        )
    
    return thread

@router.post("/chat/thread", response_model=dict)
async def create_chat_thread(current_user: dict = Depends(get_current_user)):
    """Create a new chat thread for a user"""
    user_id = str(current_user["_id"])
    user_name = current_user.get("name", "User")
    role = current_user.get("role", "user")
    
    logger.info(f"Creating new chat thread for user {user_id} with role {role}")
    
    if role == "admin":
        raise HTTPException(status_code=400, detail="Admins cannot create chat threads")
    
    existing_thread = await mongodb_service.find_with_conditions(
        collection_name="chat_threads",
        conditions={"user_id": user_id}
    )
    
    if existing_thread and len(existing_thread) > 0:
        logger.info(f"Found existing thread for user {user_id}: {existing_thread[0]['_id']}")
        return existing_thread[0]
    
    new_thread = {
        "user_id": user_id,  
        "user_email": current_user.get("email", "unknown@example.com"),
        "user_name": user_name,  
        "admin_id": None,
        "messages": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    logger.info(f"Creating new thread with data: {new_thread}")
    
    thread_id = await mongodb_service.insert_one(
        collection_name="chat_threads",
        document=new_thread
    )
    
    new_thread["_id"] = thread_id
    logger.info(f"Created thread with ID: {thread_id}")
    return new_thread

@router.post("/chat/thread/{thread_id}/message", response_model=dict)
async def add_message_to_thread(
    thread_id: str,
    message: dict,
    current_user: dict = Depends(get_current_user)
):
    """Add a new message to a chat thread"""
    logger.info(f"Received message: {message}")
    logger.info(f"Current user: {current_user}")
    user_id = str(current_user["_id"])
    user_name = current_user.get("name", "User")
    role = current_user.get("role", "user")

    thread = await mongodb_service.find_by_id(
        collection_name="chat_threads",
        id=ObjectId(thread_id)
    )

    if not thread:
        raise HTTPException(status_code=404, detail="Chat thread not found")

    if role != "admin" and thread["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this chat thread")

    if role == "admin":
        user_in_thread = await mongodb_service.find_by_id(
            collection_name="users",
            id=ObjectId(thread["user_id"])
        )
        if user_in_thread and user_in_thread.get("role") == "admin":
            raise HTTPException(status_code=400, detail="Admins cannot send messages to other admins.")

    if role == "user" and thread["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to send messages to this thread")  
    new_message = {
        "sender_id": user_id,
        "sender_name": user_name,
        "sender_role": role,
        "content": message.get("content", ""),
        "timestamp": datetime.utcnow(),
        "is_read": False
    }

    logger.info(f"Adding new message from {role} user {user_name} (ID: {user_id}): {new_message}")

    messages = thread.get("messages", [])
    messages.append(new_message)

    await mongodb_service.update_one(
        collection_name="chat_threads",
        query={"_id": ObjectId(thread_id)},
        update={
            "messages": messages,
            "updated_at": datetime.utcnow()
        }
    )
    notify_payload = {
        "type": "new_message",
        "thread_id": thread_id,
        "message": new_message
    }
    
    if role == "admin":
        recipient_id = thread["user_id"]
        await manager.send_personal_message(notify_payload, recipient_id)
    else:
        await manager.broadcast_to_admins(notify_payload)

    recipient_id = thread["user_id"] if role == "admin" else None
    if recipient_id:
        notify_payload = {
            "type": "new_message",
            "thread_id": thread_id,
            "message": new_message
        }
        await manager.send_personal_message(notify_payload, recipient_id)

    return {"message": "Message added successfully", "thread_id": thread_id}

@router.websocket("/ws/chat/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, role: Optional[str] = Query(None)):
    try:
        is_admin = role == "admin"
        if is_admin:
            user = await mongodb_service.find_by_id(
                collection_name="users",
                id=ObjectId(user_id)
            )
            if not user or user.get("role") != "admin":
                logger.warning(f"User {user_id} claiming to be admin but doesn't have admin role")
                await websocket.close(code=4003, reason="Unauthorized")
                return
        await manager.connect(websocket, user_id, is_admin)
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "user_id": user_id,
            "is_admin": is_admin,
            "timestamp": datetime.utcnow().isoformat()
        }))
        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                message_type = message_data.get("type", "message")
                if message_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
        except WebSocketDisconnect:
            manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(user_id)
