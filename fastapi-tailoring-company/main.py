from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, materials

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

# Include routers
app.include_router(auth.router)
app.include_router(materials.router)
