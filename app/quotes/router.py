"""
3i Fund Portal — WebSocket Proxy for Real-Time Quotes
Proxies the on-prem quote WebSocket to authenticated frontend clients.
"""

import asyncio
import json
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import websockets

from app.auth.jwt import decode_access_token
from app.config import settings
from app.dealterms import repository as dealterms

logger = logging.getLogger("portal.quotes")
router = APIRouter()


def _get_onprem_ws_url() -> str:
    """Derive the on-prem WebSocket URL from the HTTP base URL."""
    parsed = urlparse(settings.onprem_base_url)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    url = f"{ws_scheme}://{parsed.netloc}/ws/quotes"
    logger.debug("On-prem WS URL: %s", url)
    return url


@router.websocket("/quotes")
async def websocket_quotes(websocket: WebSocket, token: str = ""):
    """
    Proxy WebSocket for real-time quote streaming.
    Frontend connects with ?token=JWT, backend validates and relays
    to the on-prem quote feed for the user's company symbol.
    """
    client_host = websocket.client.host if websocket.client else "unknown"
    logger.info("WS /quotes connection from %s", client_host)

    # Validate JWT token
    if not token:
        logger.warning("WS /quotes: no token provided from %s", client_host)
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    try:
        payload = decode_access_token(token)
        logger.info("WS /quotes: JWT valid, user_id=%s company_id=%s",
                     payload.get("user_id"), payload.get("company_id"))
    except Exception as exc:
        logger.warning("WS /quotes: JWT validation failed from %s: %s", client_host, exc)
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    company_id = payload.get("company_id")
    if not company_id:
        logger.warning("WS /quotes: no company_id in JWT for user=%s", payload.get("user_id"))
        await websocket.close(code=4002, reason="No company assigned")
        return

    # Look up company symbol
    company = await dealterms.get_company_by_id(int(company_id))
    if not company:
        logger.error("WS /quotes: company_id=%s not found in PostgreSQL", company_id)
        await websocket.close(code=4003, reason="Company not found")
        return

    symbol = company["symbol"]
    logger.info("WS /quotes: resolved company_id=%s → symbol=%s", company_id, symbol)

    await websocket.accept()
    logger.info("WS /quotes: connection accepted for symbol=%s", symbol)

    onprem_ws = None
    try:
        # Connect to on-prem WebSocket
        ws_url = _get_onprem_ws_url()
        logger.info("WS /quotes: connecting to on-prem at %s", ws_url)
        onprem_ws = await websockets.connect(ws_url)
        logger.info("WS /quotes: on-prem WS connected")

        # Wait for welcome message, relay it
        welcome = await onprem_ws.recv()
        logger.info("WS /quotes: received welcome from on-prem: %s", welcome[:500])
        await websocket.send_text(welcome)

        # Subscribe to the user's company symbol
        subscribe_msg = json.dumps({"symbol": symbol})
        logger.info("WS /quotes: subscribing to symbol=%s", symbol)
        await onprem_ws.send(subscribe_msg)

        # Relay messages bidirectionally
        async def relay_onprem_to_client():
            """Forward messages from on-prem to the frontend."""
            msg_count = 0
            async for message in onprem_ws:
                msg_count += 1
                if msg_count <= 5 or msg_count % 100 == 0:
                    logger.debug("WS /quotes: on-prem→client msg #%d: %s", msg_count, message[:500])
                await websocket.send_text(message)

        async def relay_client_to_onprem():
            """Forward messages from the frontend to on-prem."""
            while True:
                data = await websocket.receive_text()
                logger.debug("WS /quotes: client→on-prem: %s", data[:500])
                await onprem_ws.send(data)

        # Run both relays; when either ends, cancel the other
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(relay_onprem_to_client()),
                asyncio.create_task(relay_client_to_onprem()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        # Log which relay ended and why
        for task in done:
            exc = task.exception()
            if exc:
                logger.warning("WS /quotes: relay ended with exception: %s", exc)
            else:
                logger.info("WS /quotes: relay ended normally")

    except WebSocketDisconnect:
        logger.info("WS /quotes: client disconnected (symbol=%s)", symbol)
    except Exception as exc:
        logger.error("WS /quotes: error for symbol=%s: %s", symbol, exc, exc_info=True)
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "message": str(exc)})
            )
        except Exception:
            pass
    finally:
        if onprem_ws:
            logger.info("WS /quotes: closing on-prem WS for symbol=%s", symbol)
            await onprem_ws.close()
        logger.info("WS /quotes: session ended for symbol=%s", symbol)
