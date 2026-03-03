"""
3i Fund Portal — Admin Router
Admin-only endpoints for viewing all companies, ELOCs, and purchase notices.
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import require_admin
from app.auth.models import UserInfo
from app.database.mongo import get_db

router = APIRouter()


@router.get("/companies")
async def list_companies(admin: UserInfo = Depends(require_admin)):
    """List all companies with ELOC counts."""
    db = get_db()
    companies = []

    async for company in db["companies"].find():
        company_id = company.get("company_id", str(company.get("_id", "")))

        # Count ELOCs for this company
        total = await db["eloc_state"].count_documents({"company_id": company_id})
        active = await db["eloc_state"].count_documents(
            {"company_id": company_id, "status": "active"}
        )

        companies.append({
            "company_id": company_id,
            "name": company.get("name", ""),
            "active_elocs": active,
            "total_elocs": total,
            "last_activity": company.get("last_activity"),
        })

    return companies


@router.get("/elocs")
async def list_all_elocs(admin: UserInfo = Depends(require_admin)):
    """List all ELOCs across all companies."""
    db = get_db()
    elocs = []

    async for state_doc in db["eloc_state"].find():
        # Determine current workflow step
        steps = state_doc.get("steps", {})
        current_step = None
        for step_key, step_state in steps.items():
            if step_state in ("Pending", "Awaiting"):
                current_step = step_key
                break

        elocs.append({
            "eloc_id": state_doc.get("eloc_id", ""),
            "company_id": state_doc.get("company_id", ""),
            "company_name": state_doc.get("company_name", ""),
            "type": state_doc.get("type"),
            "status": state_doc.get("status", "active"),
            "current_workflow_step": current_step,
            "created_at": state_doc.get("created_at"),
        })

    return elocs


@router.get("/purchase-notices")
async def list_purchase_notices(admin: UserInfo = Depends(require_admin)):
    """List all purchase notices across all companies."""
    db = get_db()
    notices = []

    async for doc in db["eloc_data"].find({"step": "signed_purchase_notice_sent"}):
        document = doc.get("document", {})
        notices.append({
            "notice_id": str(doc.get("_id", "")),
            "company_id": doc.get("company_id", ""),
            "company_name": doc.get("company_name", ""),
            "eloc_id": doc.get("eloc_id", ""),
            "shares": document.get("shares", 0),
            "estimated_value": document.get("estimated_value"),
            "status": document.get("status", "submitted"),
            "submitted_at": doc.get("event_datetime"),
        })

    return notices
