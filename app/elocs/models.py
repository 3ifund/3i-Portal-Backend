"""
3i Fund Portal — ELOC Schemas
"""

from pydantic import BaseModel


class PricingPeriod(BaseModel):
    name: str
    current_price: float
    shares_available: int
    estimated_dollar_value: float


class ElocSummary(BaseModel):
    eloc_id: str
    type: str | None = None
    description: str | None = None
    status: str  # "active", "completed", "rejected"
    pricing_periods_count: int = 0
    created_at: str | None = None


class ElocDetail(BaseModel):
    eloc_id: str
    type: str | None = None
    description: str | None = None
    status: str
    pricing_periods: list[PricingPeriod] = []
    current_state: dict | None = None


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
