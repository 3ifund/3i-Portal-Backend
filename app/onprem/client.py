"""
3i Fund Portal — On-Prem Server Client
All communication with the on-premises calculation server goes through here.
"""

import httpx

from app.config import settings

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Lazily create a shared async HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.onprem_base_url,
            timeout=settings.onprem_timeout_seconds,
        )
    return _client


async def get_eloc_pricing(eloc_id: str, company_id: str) -> dict:
    """
    Fetch ELOC pricing data (pricing periods, shares, prices, estimated values)
    from the on-prem server.
    """
    client = _get_client()
    response = await client.get(
        f"/api/elocs/{eloc_id}/pricing",
        params={"company_id": company_id},
    )
    response.raise_for_status()
    return response.json()


async def get_eloc_state(eloc_id: str, company_id: str) -> dict:
    """
    Fetch the current ELOC pricing state from the on-prem server.
    """
    client = _get_client()
    response = await client.get(
        f"/api/elocs/{eloc_id}/state",
        params={"company_id": company_id},
    )
    response.raise_for_status()
    return response.json()


async def get_company_elocs(company_id: str) -> list[dict]:
    """
    Fetch the list of ELOCs for a company from the on-prem server.
    """
    client = _get_client()
    response = await client.get(
        "/api/elocs",
        params={"company_id": company_id},
    )
    response.raise_for_status()
    return response.json()


async def submit_purchase_notice(
    eloc_id: str,
    company_id: str,
    pricing_period: str,
    shares: int,
) -> dict:
    """
    Submit a purchase notice to the on-prem server.
    Returns acknowledgment response.
    """
    client = _get_client()
    response = await client.post(
        f"/api/elocs/{eloc_id}/purchase-notice",
        json={
            "company_id": company_id,
            "pricing_period": pricing_period,
            "shares": shares,
        },
    )
    response.raise_for_status()
    return response.json()
