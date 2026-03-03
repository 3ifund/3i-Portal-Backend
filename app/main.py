"""
3i Fund Portal — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.mongo import connect_mongo, close_mongo
from app.auth.router import router as auth_router
from app.elocs.router import router as elocs_router
from app.admin.router import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await connect_mongo()
    yield
    await close_mongo()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

# CORS — allow the S3-hosted frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(elocs_router, prefix="/elocs", tags=["elocs"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])


@app.get("/health")
async def health():
    return {"status": "ok"}
