"""
3i Fund Portal — ELOC Schemas
"""

from pydantic import BaseModel
from datetime import date, time


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
