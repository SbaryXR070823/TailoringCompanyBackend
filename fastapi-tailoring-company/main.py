from fastapi import FastAPI, Request, Response, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, materials, materialsHistory, models_training, models_prompt, orders, products, chat, files, stock_changes
from mongo.mongo_service import MongoDBService
from firebase.firebase_config import verify_firebase_token
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware with all possible configurations
origins = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
    "http://localhost:4000",
    "http://127.0.0.1:4000",
    "null",  # For debugging purposes
    # Add any other origins you need
]
    
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods temporarily for debugging
    allow_headers=["*"],  # Allow all headers temporarily for debugging
    expose_headers=["Content-Disposition", "Content-Type", "Content-Length"]
)
# Add a middleware to log requests for debugging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request path: {request.url.path}")
    logger.info(f"Request method: {request.method}")
    
    if logger.level <= logging.DEBUG:
        logger.debug(f"Request headers: {request.headers}")
    
    try:
        response = await call_next(request)
        
        logger.info(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        # Log any unhandled exceptions
        logger.error(f"Unhandled exception: {str(e)}")
        raise

connection_string = "mongodb://localhost:27017/TailoringDb"

mongodb_service = MongoDBService(connection_string=connection_string)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Tailoring API!"}

@app.get("/auth/verify-token")
async def verify_token_endpoint_get(request: Request):
    """Endpoint to verify a token via GET request using the Authorization header."""
    try:
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header is missing")
            
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization format. Expected 'Bearer token'")
            
        token = authorization.replace("Bearer ", "")
        decoded_token = verify_firebase_token(token)
        
        response = {
            "_id": decoded_token.get("uid", ""),
            "email": decoded_token.get("email", ""),
            "role": decoded_token.get("role", "user"),
            "name": decoded_token.get("name", ""),
            "firebase_uid": decoded_token.get("uid", ""),
            "token": token
        }
        
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Include routers
app.include_router(auth.router)
app.include_router(materials.router)
app.include_router(materialsHistory.router)
app.include_router(models_training.router) 
app.include_router(models_prompt.router) 
app.include_router(orders.router)
app.include_router(products.router)
app.include_router(chat.router)
app.include_router(files.router, prefix="")
app.include_router(stock_changes.router)