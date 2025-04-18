from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, materials, materialsHistory, models_training, models_prompt, orders, products, chat
from mongo.mongo_service import MongoDBService
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
    expose_headers=["*"]
)
# Add a middleware to log requests for debugging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log the request details
    logger.info(f"Request path: {request.url.path}")
    logger.info(f"Request method: {request.method}")
    
    # Only log headers in debug mode to avoid logging sensitive information
    if logger.level <= logging.DEBUG:
        logger.debug(f"Request headers: {request.headers}")
    
    try:
        # Process the request
        response = await call_next(request)
        
        # Let the CORS middleware handle CORS - don't duplicate headers here
        # This approach avoids conflicts between FastAPI's CORSMiddleware and manual headers
        
        # Log response status code
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

# Include routers
app.include_router(auth.router)
app.include_router(materials.router)
app.include_router(materialsHistory.router)
app.include_router(models_training.router) 
app.include_router(models_prompt.router) 
app.include_router(orders.router)
app.include_router(products.router)
app.include_router(chat.router)