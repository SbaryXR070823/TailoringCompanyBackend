from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, materials, materialsHistory, models_training, models_prompt
from mongo.mongo_service import MongoDBService

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
