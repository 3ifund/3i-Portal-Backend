"""
3i Fund Portal — WebSocket Proxy for Real-Time Quotes
Proxies the on-prem quote WebSocket to authenticated frontend clients.
"""

import asyncio
import json
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import websockets

from app.auth.jwt import decode_access_token
from app.config import settings
from app.dealterms import repository as dealterms

router = APIRouter()


def _get_onprem_ws_url() -> str:
    """Derive the on-prem WebSocket URL from the HTTP base URL."""
    parsed = urlparse(settings.onprem_base_url)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{ws_scheme}://{parsed.netloc}/ws/quotes"


@router.websocket("/quotes")
async def websocket_quotes(websocket: WebSocket, token: str = ""):
    """
    Proxy WebSocket for real-time quote streaming.
    Frontend connects with ?token=JWT, backend validates and relays
    to the on-prem quote feed for the user's company symbol.
    """
    # Validate JWT token
    try:
        payload = decode_access_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    company_id = payload.get("company_id")
    if not company_id:
        await websocket.close(code=4002, reason="No company assigned")
        return

    # Look up company symbol
    company = await dealterms.get_company_by_id(int(company_id))
    if not company:
        await websocket.close(code=4003, reason="Company not found")
        return

    symbol = company["symbol"]

    await websocket.accept()

    onprem_ws = None
    try:
        # Connect to on-prem WebSocket
        ws_url = _get_onprem_ws_url()
        onprem_ws = await websockets.connect(ws_url)

        # Wait for welcome message, relay it
        welcome = await onprem_ws.recv()
        await websocket.send_text(welcome)

        # Subscribe to the user's company symbol
        await onprem_ws.send(json.dumps({"symbol": symbol}))

        # Relay messages bidirectionally
        async def relay_onprem_to_client():
            """Forward messages from on-prem to the frontend."""
            async for message in onprem_ws:
                await websocket.send_text(message)

        async def relay_client_to_onprem():
            """Forward messages from the frontend to on-prem."""
            while True:
                data = await websocket.receive_text()
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

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "message": str(exc)})
            )
        except Exception:
            pass
    finally:
        if onprem_ws:
            await onprem_ws.close()
