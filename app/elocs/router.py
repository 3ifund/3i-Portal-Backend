"""
3i Fund Portal — ELOC Router
Endpoints for ELOC listing, detail, workflow, documents, and purchase notices.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.auth.models import UserInfo
from app.elocs import service
from app.elocs.models import (
    ElocDetail,
    ElocSummary,
    PurchaseNoticeRequest,
    PurchaseNoticeResponse,
    WorkflowResponse,
)

router = APIRouter()


@router.get("", response_model=list[ElocSummary])
async def list_elocs(
    status_filter: str | None = Query(None, alias="status"),
    user: UserInfo = Depends(get_current_user),
):
    """List ELOCs for the authenticated user's company."""
    company_id = int(user.company_id) if user.company_id else None
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no company_id assigned",
        )
    elocs = await service.get_company_elocs(company_id, status_filter)
    return elocs


@router.get("/shares-available")
async def get_shares_available(
    user: UserInfo = Depends(get_current_user),
):
    """Get available shares for all pricing periods from on-prem server."""
    company_id = int(user.company_id) if user.company_id else None
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no company_id assigned",
        )
    try:
        return await service.get_shares_available(company_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to fetch shares available: {exc}",
        )


@router.get("/{eloc_id}", response_model=ElocDetail)
async def get_eloc(
    eloc_id: int,
    user: UserInfo = Depends(get_current_user),
):
    """Get ELOC detail: pricing periods, shares, deal terms."""
    company_id = int(user.company_id) if user.company_id else None
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no company_id assigned",
        )
    detail = await service.get_eloc_detail(eloc_id, company_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ELOC deal not found",
        )
    return detail


@router.get("/{eloc_id}/workflow", response_model=WorkflowResponse)
async def get_workflow(
    eloc_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """Get workflow state and event data from MongoDB."""
    workflow = await service.get_eloc_workflow(eloc_id)
    return workflow


@router.get("/{eloc_id}/documents/{step}")
async def get_document(
    eloc_id: str,
    step: str,
    user: UserInfo = Depends(get_current_user),
):
    """Get the document for a specific workflow step."""
    doc = await service.get_eloc_document(eloc_id, step)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found for this step",
        )
    return doc


@router.post("/{eloc_id}/purchase-notice", response_model=PurchaseNoticeResponse)
async def submit_purchase_notice(
    eloc_id: str,
    request: PurchaseNoticeRequest,
    user: UserInfo = Depends(get_current_user),
):
    """Submit a purchase notice to the on-prem server."""
    if request.shares < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shares must be at least 1",
        )

    try:
        result = await service.submit_purchase_notice(
            eloc_id, user.company_id, request.pricing_period, request.shares
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to submit purchase notice: {exc}",
        )

    return PurchaseNoticeResponse(
        status=result.get("status", "acknowledged"),
        message=result.get("message", "Purchase notice submitted successfully"),
    )
