"""Market and industry endpoints."""

from __future__ import annotations

from typing import Any

from eve_esi.client import ESIClient


def get_character_orders(client: ESIClient) -> list[dict[str, Any]]:
    """Get active market orders of the authenticated character.

    Returns list of orders with:
        - order_id, type_id, location_id, price, volume_remain, volume_total
        - is_buy_order, issued, duration, range, min_volume
    """
    return client.get(f"/characters/{client.character_id}/orders/")


def get_character_order_history(client: ESIClient) -> list[dict[str, Any]]:
    """Get historical market orders of the authenticated character."""
    return client.get_paginated(f"/characters/{client.character_id}/orders/history/")


def get_market_prices(client: ESIClient) -> list[dict[str, Any]]:
    """Get average and adjusted prices for all tradeable items.

    Returns list of {type_id, average_price, adjusted_price}.
    """
    return client.get("/markets/prices/", authenticated=False)


def get_market_orders_region(
    client: ESIClient,
    region_id: int,
    type_id: int | None = None,
    order_type: str = "all",
) -> list[dict[str, Any]]:
    """Get market orders in a region.

    Args:
        region_id: Region ID (e.g., 10000002 for The Forge/Jita)
        type_id: Optional type ID to filter by
        order_type: 'buy', 'sell', or 'all'
    """
    params: dict[str, Any] = {"order_type": order_type}
    if type_id is not None:
        params["type_id"] = type_id
    return client.get_paginated(
        f"/markets/{region_id}/orders/",
        authenticated=False,
        params=params,
    )


def get_market_history(
    client: ESIClient, region_id: int, type_id: int
) -> list[dict[str, Any]]:
    """Get market history for a type in a region.

    Returns list of daily summaries: {date, average, highest, lowest, volume, order_count}.
    """
    return client.get(
        f"/markets/{region_id}/history/",
        authenticated=False,
        params={"type_id": type_id},
    )


def get_blueprints(client: ESIClient) -> list[dict[str, Any]]:
    """Get blueprints owned by the authenticated character.

    Returns list of blueprints with:
        - item_id, type_id, location_id, location_flag
        - quantity, material_efficiency, time_efficiency, runs
    """
    return client.get_paginated(f"/characters/{client.character_id}/blueprints/")


def get_industry_jobs(client: ESIClient, include_completed: bool = False) -> list[dict[str, Any]]:
    """Get industry jobs of the authenticated character.

    Returns list of jobs with:
        - job_id, activity_id, blueprint_id, blueprint_type_id
        - status, start_date, end_date, runs, output_location_id
    """
    params = {"include_completed": str(include_completed).lower()}
    return client.get(f"/characters/{client.character_id}/industry/jobs/", params=params)


def get_contracts(client: ESIClient) -> list[dict[str, Any]]:
    """Get contracts of the authenticated character."""
    return client.get_paginated(f"/characters/{client.character_id}/contracts/")

