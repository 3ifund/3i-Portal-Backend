"""
3i Fund Portal — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.mongo import connect_mongo, close_mongo
from app.database.postgres import connect_postgres, close_postgres
from app.auth.router import router as auth_router
from app.elocs.router import router as elocs_router
from app.admin.router import router as admin_router
from app.quotes.router import router as quotes_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await connect_mongo()
    await connect_postgres()
    yield
    await close_postgres()
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
app.include_router(quotes_router, prefix="/ws", tags=["quotes"])


@app.get("/health")
async def health():
    return {"status": "ok"}
