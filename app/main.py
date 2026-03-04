"""
3i Fund Portal — FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import setup_logging
from app.database.mongo import connect_mongo, close_mongo
from app.database.postgres import connect_postgres, close_postgres
from app.auth.router import router as auth_router
from app.elocs.router import router as elocs_router
from app.admin.router import router as admin_router
from app.quotes.router import router as quotes_router

# Initialize logging before anything else
setup_logging()
logger = logging.getLogger("portal.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("=== 3i Fund Portal starting up ===")
    logger.info("CORS origins: %s", settings.cors_origins)
    logger.info("On-prem base URL: %s", settings.onprem_base_url)
    logger.info("MongoDB URI: %s", settings.mongo_uri)
    logger.info("PostgreSQL: %s@%s:%s/%s", settings.pg_user, settings.pg_host, settings.pg_port, settings.pg_database)

    await connect_mongo()
    logger.info("MongoDB connected")
    await connect_postgres()
    logger.info("PostgreSQL connected")

    yield

    logger.info("=== 3i Fund Portal shutting down ===")
    await close_postgres()
    logger.info("PostgreSQL disconnected")
    await close_mongo()
    logger.info("MongoDB disconnected")


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
