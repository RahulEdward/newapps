from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from database.session import engine, Base
from database import models # Import models to register them with Base
from charts import models as charts_models  # Historical data models
from routers.auth import router as auth_router
from routers.broker import router as broker_router
from routers.angel_one import router as angel_one_router
from charts.router import router as data_router  # Historical Data Management
from utils.scheduler import scheduler_manager  # Scheduler for automated downloads

# Create database tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events"""
    # Startup: Initialize scheduler
    scheduler_manager.init_app()
    yield
    # Shutdown: Stop scheduler
    scheduler_manager.shutdown()

app = FastAPI(
    title="Trading Maven API",
    description="Backend API for institutional-grade trading app",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration for Frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(broker_router)
app.include_router(angel_one_router)
app.include_router(data_router)  # Historical Data Management


@app.get("/")
async def root():
    return {"status": "online", "message": "QuantFlow API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
