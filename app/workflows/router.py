"""
3i Fund Portal — Workflow WebSocket & MongoDB Change Stream
Pushes real-time workflow state updates to connected frontend clients.
Watches the eloc_state collection for changes made by external C# apps.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth.jwt import decode_access_token
from app.database.mongo import eloc_state_collection
from app.elocs.models import build_workflow_steps

logger = logging.getLogger("portal.workflows")
router = APIRouter()

# ---- Connection Manager ----

# Maps company_id → set of connected WebSockets
_connections: dict[int, set[WebSocket]] = {}


def _register(company_id: int, ws: WebSocket):
    if company_id not in _connections:
        _connections[company_id] = set()
    _connections[company_id].add(ws)
    logger.info("WS /workflows: registered client for company_id=%s (%d total)",
                company_id, len(_connections[company_id]))


def _unregister(company_id: int, ws: WebSocket):
    if company_id in _connections:
        _connections[company_id].discard(ws)
        if not _connections[company_id]:
            del _connections[company_id]
    logger.info("WS /workflows: unregistered client for company_id=%s", company_id)


async def _broadcast(company_id: int, data: dict):
    """Send a message to all connected clients for a company."""
    clients = _connections.get(company_id, set()).copy()
    if not clients:
        return

    message = json.dumps(data)
    dead = []
    for ws in clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)

    for ws in dead:
        _unregister(company_id, ws)

    if clients:
        logger.debug("WS /workflows: broadcast to %d clients for company_id=%s",
                      len(clients) - len(dead), company_id)


# ---- WebSocket Endpoint ----

@router.websocket("/workflows")
async def websocket_workflows(websocket: WebSocket, token: str = ""):
    """
    WebSocket for real-time workflow state updates.
    Frontend connects with ?token=JWT. Backend pushes workflow_update
    and workflow_removed messages when MongoDB eloc_state changes.
    """
    client_host = websocket.client.host if websocket.client else "unknown"
    logger.info("WS /workflows connection from %s", client_host)

    # Validate JWT token
    if not token:
        logger.warning("WS /workflows: no token provided from %s", client_host)
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    try:
        payload = decode_access_token(token)
        logger.info("WS /workflows: JWT valid, user_id=%s company_id=%s",
                     payload.get("user_id"), payload.get("company_id"))
    except Exception as exc:
        logger.warning("WS /workflows: JWT validation failed from %s: %s", client_host, exc)
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    company_id = payload.get("company_id")
    if not company_id:
        logger.warning("WS /workflows: no company_id in JWT for user=%s", payload.get("user_id"))
        await websocket.close(code=4002, reason="No company assigned")
        return

    company_id = int(company_id)
    await websocket.accept()
    _register(company_id, websocket)

    # Send current workflow state on connect
    try:
        await _send_initial_state(company_id, websocket)
    except Exception as exc:
        logger.warning("WS /workflows: failed to send initial state: %s", exc)

    try:
        # Keep connection alive — just wait for client disconnect
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WS /workflows: client disconnected (company_id=%s)", company_id)
    except Exception as exc:
        logger.warning("WS /workflows: connection error: %s", exc)
    finally:
        _unregister(company_id, websocket)


# ---- Initial State & Resync ----

async def _send_initial_state(company_id: int, ws: WebSocket):
    """Send all include=true workflows to a newly connected client."""
    cursor = eloc_state_collection().find({"company_id": company_id, "include": True})
    count = 0
    async for doc in cursor:
        message = _build_workflow_message(doc)
        await ws.send_text(json.dumps(message))
        count += 1
    logger.info("WS /workflows: sent %d initial workflows to company_id=%s", count, company_id)


async def _resync_all_clients():
    """
    Broadcast current state to all connected clients.
    Called when Change Stream reconnects without a resume token,
    to catch any changes that occurred during the gap.
    """
    if not _connections:
        return

    logger.info("Change Stream: resyncing all connected clients (%d companies)", len(_connections))
    for company_id, clients in list(_connections.items()):
        cursor = eloc_state_collection().find({"company_id": company_id, "include": True})
        async for doc in cursor:
            message = _build_workflow_message(doc)
            await _broadcast(company_id, message)


# ---- MongoDB Change Stream Watcher ----

def _build_workflow_message(doc: dict) -> dict:
    """Build a workflow_update message from an eloc_state document."""
    current_step = doc.get("current_step", "")
    step_status = doc.get("step_status", "pending")
    steps, can_remove = build_workflow_steps(current_step, step_status)

    return {
        "type": "workflow_update",
        "workflow": {
            "eloc_id": str(doc["eloc_id"]),
            "company_id": doc["company_id"],
            "current_step": current_step,
            "step_status": step_status,
            "updated_at": str(doc["updated_at"]) if doc.get("updated_at") else None,
            "can_remove": can_remove,
            "steps": steps,
        },
    }


async def watch_eloc_state_changes():
    """
    Background task: watch MongoDB eloc_state collection for changes.
    Broadcasts workflow updates to connected WebSocket clients.
    Reconnects with exponential backoff on failure.
    """
    delay = 2
    max_delay = 30
    resume_token = None

    while True:
        try:
            logger.info("Change Stream: opening watch on eloc_state (resume_token=%s)",
                        "yes" if resume_token else "no")

            pipeline = []
            watch_kwargs = {
                "pipeline": pipeline,
                "full_document": "updateLookup",
            }
            if resume_token:
                watch_kwargs["resume_after"] = resume_token

            async with eloc_state_collection().watch(**watch_kwargs) as stream:
                delay = 2  # Reset backoff on successful connection
                logger.info("Change Stream: watching eloc_state collection")

                # If reconnecting without a resume token, resync all clients
                # to catch any changes that occurred during the gap
                if not resume_token:
                    await _resync_all_clients()

                async for change in stream:
                    resume_token = stream.resume_token
                    op_type = change.get("operationType")
                    full_doc = change.get("fullDocument")

                    if not full_doc:
                        logger.debug("Change Stream: %s event without fullDocument", op_type)
                        continue

                    company_id = full_doc.get("company_id")
                    eloc_id = str(full_doc.get("eloc_id", ""))

                    if not company_id:
                        logger.debug("Change Stream: skipping doc without company_id")
                        continue

                    logger.info("Change Stream: %s on eloc_id=%s company_id=%s include=%s",
                                op_type, eloc_id, company_id, full_doc.get("include"))

                    if full_doc.get("include"):
                        # Send workflow update
                        message = _build_workflow_message(full_doc)
                        await _broadcast(int(company_id), message)
                    else:
                        # include is false — send removal
                        await _broadcast(int(company_id), {
                            "type": "workflow_removed",
                            "eloc_id": eloc_id,
                        })

        except asyncio.CancelledError:
            logger.info("Change Stream: watcher task cancelled")
            break
        except Exception as exc:
            logger.error("Change Stream: error: %s (retry in %ds)", exc, delay, exc_info=True)
            # Clear resume token — next reconnect will do a full resync
            resume_token = None
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)
