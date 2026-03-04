"""
3i Fund Portal — MongoDB Connection
Uses motor (async MongoDB driver) to connect to the on-prem MongoDB.
Collections: eloc_state, eloc_data
"""

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

logger = logging.getLogger("portal.db.mongo")
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_mongo():
    """Open the MongoDB connection on app startup."""
    global _client, _db
    logger.info("Connecting to MongoDB at %s (db=%s)", settings.mongo_uri, settings.mongo_db_name)
    _client = AsyncIOMotorClient(settings.mongo_uri)
    _db = _client[settings.mongo_db_name]
    # Verify connection
    try:
        await _client.admin.command("ping")
        logger.info("MongoDB ping OK")
    except Exception as exc:
        logger.error("MongoDB ping FAILED: %s", exc)


async def close_mongo():
    """Close the MongoDB connection on app shutdown."""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed")


def get_db() -> AsyncIOMotorDatabase:
    """Return the database instance. Call after connect_mongo()."""
    if _db is None:
        raise RuntimeError("MongoDB not connected. Call connect_mongo() first.")
    return _db


def eloc_state_collection():
    """Return the eloc_state collection."""
    return get_db()["eloc_state"]


def eloc_data_collection():
    """Return the eloc_data collection."""
    return get_db()["eloc_data"]
