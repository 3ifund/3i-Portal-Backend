"""
3i Fund Portal — ELOC Schemas
"""

from enum import Enum

from pydantic import BaseModel
from datetime import date, time


# ---- Workflow Enums ----

class WorkflowStepEnum(str, Enum):
    """The 6 sequential steps of the ELOC workflow."""
    signed_purchase_notice_sent = "signed_purchase_notice_sent"
    eloc_terms_verified = "eloc_terms_verified"
    purchase_notice_countersigned = "purchase_notice_countersigned"
    eloc_awaiting_end_of_pricing_period = "eloc_awaiting_end_of_pricing_period"
    final_pricing = "final_pricing"
    company_countersigns_confirmation = "company_countersigns_confirmation"


class StepStatusEnum(str, Enum):
    """Status of the current workflow step."""
    pending = "pending"
    completed = "completed"
    rejected = "rejected"


# Ordered list for index-based comparison
WORKFLOW_STEPS_ORDERED = list(WorkflowStepEnum)

# Human-readable labels for each step
WORKFLOW_STEP_LABELS = {
    WorkflowStepEnum.signed_purchase_notice_sent: "Signed Purchase Notice Sent",
    WorkflowStepEnum.eloc_terms_verified: "ELOC Terms Verified",
    WorkflowStepEnum.purchase_notice_countersigned: "Purchase Notice Countersigned",
    WorkflowStepEnum.eloc_awaiting_end_of_pricing_period: "Awaiting End of Pricing Period",
    WorkflowStepEnum.final_pricing: "Final Pricing (Signed Confirmation Sent)",
    WorkflowStepEnum.company_countersigns_confirmation: "Company Countersigns Confirmation",
}


def build_workflow_steps(current_step: str, step_status: str) -> tuple[list[dict], bool]:
    """
    Derive all 6 step statuses from the current step and its status.
    Returns (steps_list, can_remove).

    Rules:
    - Steps before current_step → "completed"
    - current_step → step_status value (pending/completed/rejected)
    - Steps after current_step → "awaiting" (not started)
    - can_remove = True if rejected OR (last step AND completed)
    """
    try:
        current_idx = WORKFLOW_STEPS_ORDERED.index(WorkflowStepEnum(current_step))
    except (ValueError, KeyError):
        current_idx = -1

    last_idx = len(WORKFLOW_STEPS_ORDERED) - 1
    steps = []

    for i, step in enumerate(WORKFLOW_STEPS_ORDERED):
        if i < current_idx:
            status = "completed"
        elif i == current_idx:
            status = step_status
        else:
            status = "awaiting"

        steps.append({
            "key": step.value,
            "label": WORKFLOW_STEP_LABELS[step],
            "status": status,
        })

    can_remove = (
        step_status == StepStatusEnum.rejected.value
        or (current_idx == last_idx and step_status == StepStatusEnum.completed.value)
    )

    return steps, can_remove


class PricingPeriod(BaseModel):
    pricing_period_id: int
    period_type: str  # e.g. "ThreeDay", "Intraday"
    dollar_cap_per_notice: float
    discount_multiplier: float
    volume_pct_cap: float | None = None
    acceptance_window_start: time | None = None
    acceptance_window_end: time | None = None
    use_half_days: bool = False


class ElocSummary(BaseModel):
    eloc_id: int
    company_id: int
    company_symbol: str | None = None
    company_name: str | None = None
    total_commitment: float
    total_commitment_remaining: float
    registered_shares_available: int
    expiration_date: date | None = None
    status: str  # "active", "completed", "expired"
    pricing_period_types: list[str] = []
    pricing_periods_count: int = 0


class ElocDetail(BaseModel):
    eloc_id: int
    company_id: int
    company_symbol: str | None = None
    company_name: str | None = None
    total_commitment: float
    total_commitment_used: float
    total_commitment_remaining: float
    registered_shares: int
    registered_shares_used: int
    registered_shares_available: int
    expiration_date: date | None = None
    min_trading_days_between_notices: int = 1
    threshold_price: float | None = None
    beneficial_ownership_limit_pct: float | None = None
    current_shares_outstanding: int | None = None
    status: str
    pricing_periods: list[PricingPeriod] = []


class WorkflowStep(BaseModel):
    key: str
    state: str  # "Awaiting", "Pending", "Completed", "Rejected"
    event_datetime: str | None = None
    has_document: bool = False


class WorkflowResponse(BaseModel):
    eloc_id: str
    steps: dict[str, str]  # step_key -> state
    events: dict[str, dict] = {}  # step_key -> {event_datetime, ...}


class PurchaseNoticeRequest(BaseModel):
    pricing_period: str
    shares: int


class PurchaseNoticeResponse(BaseModel):
    status: str
    message: str


class PricingWorkflowState(BaseModel):
    """Workflow state for an ELOC currently pricing."""
    eloc_id: str
    company_id: int
    current_step: str
    step_status: str
    updated_at: str | None = None
    can_remove: bool = False
    steps: list[dict] = []
