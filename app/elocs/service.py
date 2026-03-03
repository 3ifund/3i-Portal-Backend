"""
3i Fund Portal — ELOC Service Layer
Orchestrates data from PostgreSQL DealTerms DB (deals/pricing),
MongoDB (workflow state), and on-prem server (purchase notices).
"""

from datetime import date

from app.database.mongo import eloc_state_collection, eloc_data_collection
from app.dealterms import repository as dealterms
from app.onprem import client as onprem


def _deal_status(deal: dict) -> str:
    """Derive a display status from a deal row."""
    remaining = deal.get("total_commitment_remaining", 0)
    if remaining <= 0:
        return "completed"
    exp = deal.get("expiration_date")
    if exp and exp < date.today():
        return "expired"
    return "active"


async def get_company_elocs(company_id: int, status_filter: str | None = None) -> list[dict]:
    """
    Fetch ELOC deals from PostgreSQL DealTerms DB and enrich with
    workflow state from MongoDB.
    """
    deals = await dealterms.get_all_deals_with_pricing(company_id)
    company = await dealterms.get_company_by_id(company_id)
    company_symbol = company["symbol"] if company else None
    company_name = company["name"] if company else None

    enriched = []
    for deal in deals:
        status = _deal_status(deal)

        if status_filter == "active" and status != "active":
            continue
        if status_filter == "history" and status == "active":
            continue

        eloc_id = str(deal["eloc_deal_id"])

        # Enrich with workflow state from MongoDB
        state_doc = await eloc_state_collection().find_one({"eloc_id": eloc_id})
        workflow_state = state_doc.get("steps", {}) if state_doc else {}

        enriched.append({
            "eloc_id": deal["eloc_deal_id"],
            "company_id": deal["company_id"],
            "company_symbol": company_symbol,
            "company_name": company_name,
            "total_commitment": float(deal["total_commitment"]),
            "total_commitment_remaining": float(deal["total_commitment_remaining"]),
            "registered_shares_available": deal["registered_shares_available"],
            "expiration_date": deal.get("expiration_date"),
            "status": status,
            "pricing_period_types": [pp["period_type"] for pp in deal.get("pricing_periods", [])],
            "pricing_periods_count": len(deal.get("pricing_periods", [])),
            "workflow_state": workflow_state,
        })

    return enriched


async def get_eloc_detail(eloc_id: int, company_id: int) -> dict:
    """
    Fetch full ELOC detail from PostgreSQL: deal terms + pricing periods.
    """
    deal = await dealterms.get_deal_by_id(eloc_id)
    if not deal:
        return {}

    company = await dealterms.get_company_by_id(company_id)
    pricing_periods = await dealterms.get_pricing_periods_for_deal(eloc_id)

    return {
        "eloc_id": deal["eloc_deal_id"],
        "company_id": deal["company_id"],
        "company_symbol": company["symbol"] if company else None,
        "company_name": company["name"] if company else None,
        "total_commitment": float(deal["total_commitment"]),
        "total_commitment_used": float(deal["total_commitment_used"]),
        "total_commitment_remaining": float(deal["total_commitment_remaining"]),
        "registered_shares": deal["registered_shares"],
        "registered_shares_used": deal["registered_shares_used"],
        "registered_shares_available": deal["registered_shares_available"],
        "expiration_date": deal.get("expiration_date"),
        "min_trading_days_between_notices": deal.get("min_trading_days_between_notices", 1),
        "threshold_price": float(deal["threshold_price"]) if deal.get("threshold_price") else None,
        "beneficial_ownership_limit_pct": float(deal["beneficial_ownership_limit_pct"]) if deal.get("beneficial_ownership_limit_pct") else None,
        "current_shares_outstanding": deal.get("current_shares_outstanding"),
        "status": _deal_status(deal),
        "pricing_periods": [
            {
                "pricing_period_id": pp["pricing_period_id"],
                "period_type": pp["period_type"],
                "dollar_cap_per_notice": float(pp["dollar_cap_per_notice"]) if pp.get("dollar_cap_per_notice") else 0,
                "discount_multiplier": float(pp["discount_multiplier"]) if pp.get("discount_multiplier") else 0,
                "volume_pct_cap": float(pp["volume_pct_cap"]) if pp.get("volume_pct_cap") else None,
                "acceptance_window_start": pp.get("notice_acceptance_start_time"),
                "acceptance_window_end": pp.get("notice_acceptance_end_time"),
                "use_half_days": pp.get("use_half_days", False),
            }
            for pp in pricing_periods
        ],
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

    result = doc.get("document", {})
    if isinstance(result, dict):
        result["event_datetime"] = doc.get("event_datetime")
    return result


async def get_shares_available(company_id: int) -> dict:
    """
    Fetch available shares for all pricing periods from the on-prem server.
    Looks up company symbol from PostgreSQL, then proxies to on-prem.
    """
    company = await dealterms.get_company_by_id(company_id)
    if not company:
        return {"error": "Company not found"}
    return await onprem.get_shares_available(company["symbol"])


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
