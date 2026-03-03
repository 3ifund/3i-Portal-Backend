"""
3i Fund Portal — DealTerms Repository
Queries the on-prem PostgreSQL DealTerms database for company, ELOC deal,
and pricing period data.
"""

from app.database.postgres import get_pool


async def get_company_by_id(company_id: int) -> dict | None:
    """Fetch a company by its numeric company_id."""
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT company_id, symbol, name, name_normalized, currency
        FROM company
        WHERE company_id = $1
        """,
        company_id,
    )
    return dict(row) if row else None


async def get_company_by_symbol(symbol: str) -> dict | None:
    """Fetch a company by its ticker symbol."""
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT company_id, symbol, name, name_normalized, currency
        FROM company
        WHERE symbol = $1
        """,
        symbol,
    )
    return dict(row) if row else None


async def get_active_deals_for_company(company_id: int) -> list[dict]:
    """
    Fetch all active ELOC deals for a company.
    A deal is active if it has remaining commitment and hasn't expired.
    """
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT
            eloc_deal_id,
            company_id,
            total_commitment,
            total_commitment_used,
            total_commitment_remaining,
            registered_shares,
            registered_shares_used,
            registered_shares_available,
            expiration_date,
            min_trading_days_between_notices,
            threshold_price,
            beneficial_ownership_limit_pct,
            current_shares_outstanding
        FROM eloc_deal
        WHERE company_id = $1
          AND total_commitment_remaining > 0
        ORDER BY eloc_deal_id
        """,
        company_id,
    )
    return [dict(r) for r in rows]


async def get_deal_by_id(deal_id: int) -> dict | None:
    """Fetch a single ELOC deal by its ID."""
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT
            eloc_deal_id,
            company_id,
            total_commitment,
            total_commitment_used,
            total_commitment_remaining,
            registered_shares,
            registered_shares_used,
            registered_shares_available,
            expiration_date,
            min_trading_days_between_notices,
            threshold_price,
            beneficial_ownership_limit_pct,
            current_shares_outstanding
        FROM eloc_deal
        WHERE eloc_deal_id = $1
        """,
        deal_id,
    )
    return dict(row) if row else None


async def get_pricing_periods_for_deal(deal_id: int) -> list[dict]:
    """Fetch all pricing periods for a given ELOC deal."""
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT
            pricing_period_id,
            eloc_deal_id,
            period_type,
            volume_pct_cap,
            dollar_cap_per_notice,
            discount_multiplier,
            notice_acceptance_start_time,
            notice_acceptance_end_time,
            use_half_days
        FROM eloc_pricing_period
        WHERE eloc_deal_id = $1
        ORDER BY pricing_period_id
        """,
        deal_id,
    )
    return [dict(r) for r in rows]


async def get_all_deals_with_pricing(company_id: int) -> list[dict]:
    """
    Fetch all active deals for a company, each enriched with its pricing periods.
    This is the primary query used by the ELOC listing and detail endpoints.
    """
    deals = await get_active_deals_for_company(company_id)

    for deal in deals:
        deal["pricing_periods"] = await get_pricing_periods_for_deal(
            deal["eloc_deal_id"]
        )

    return deals
