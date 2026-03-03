"""
3i Fund Portal — ELOC Service Layer
Orchestrates data from on-prem server (pricing/shares) and MongoDB (workflow state).
"""

from app.database.mongo import eloc_state_collection, eloc_data_collection
from app.onprem import client as onprem


async def get_company_elocs(company_id: str, status_filter: str | None = None) -> list[dict]:
    """
    Fetch ELOCs from on-prem and enrich with workflow state from MongoDB.
    Optionally filter by status ('active' or 'history').
    """
    elocs = await onprem.get_company_elocs(company_id)

    # Enrich with workflow state from MongoDB
    enriched = []
    for eloc in elocs:
        eloc_id = eloc.get("eloc_id")
        state_doc = await eloc_state_collection().find_one({"eloc_id": eloc_id})

        if state_doc:
            eloc["workflow_state"] = state_doc.get("steps", {})

        if status_filter == "active" and eloc.get("status") != "active":
            continue
        if status_filter == "history" and eloc.get("status") == "active":
            continue

        enriched.append(eloc)

    return enriched


async def get_eloc_detail(eloc_id: str, company_id: str) -> dict:
    """
    Fetch full ELOC detail: pricing periods from on-prem, state from on-prem.
    """
    pricing = await onprem.get_eloc_pricing(eloc_id, company_id)
    state = await onprem.get_eloc_state(eloc_id, company_id)

    return {
        **pricing,
        "current_state": state,
    }


async def get_eloc_workflow(eloc_id: str) -> dict:
    """
    Fetch workflow state and events from MongoDB.
    Returns step states and event data (timestamps, documents).
    """
    state_doc = await eloc_state_collection().find_one({"eloc_id": eloc_id})
    steps = state_doc.get("steps", {}) if state_doc else {}

    # Fetch event data for each step
    events = {}
    cursor = eloc_data_collection().find({"eloc_id": eloc_id})
    async for doc in cursor:
        step_key = doc.get("step")
        if step_key:
            events[step_key] = {
                "event_datetime": doc.get("event_datetime"),
                "has_document": bool(doc.get("document")),
            }

    return {
        "eloc_id": eloc_id,
        "steps": steps,
        "events": events,
    }


async def get_eloc_document(eloc_id: str, step: str) -> dict | None:
    """
    Fetch the document associated with a specific workflow step from MongoDB.
    """
    doc = await eloc_data_collection().find_one(
        {"eloc_id": eloc_id, "step": step},
    )
    if not doc:
        return None

    # Convert ObjectId to string for serialization
    result = doc.get("document", {})
    if isinstance(result, dict):
        result["event_datetime"] = doc.get("event_datetime")
    return result


async def submit_purchase_notice(
    eloc_id: str,
    company_id: str,
    pricing_period: str,
    shares: int,
) -> dict:
    """
    Forward purchase notice to on-prem server and return acknowledgment.
    """
    return await onprem.submit_purchase_notice(eloc_id, company_id, pricing_period, shares)
