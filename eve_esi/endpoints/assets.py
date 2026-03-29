"""Asset management endpoints."""

from __future__ import annotations

from typing import Any

from eve_esi.client import ESIClient


def get_assets(client: ESIClient) -> list[dict[str, Any]]:
    """Get all assets of the authenticated character (paginated).

    Returns list of items with:
        - item_id, type_id, location_id, location_type, location_flag
        - quantity, is_singleton, is_blueprint_copy
    """
    return client.get_paginated(f"/characters/{client.character_id}/assets/")


def get_asset_names(client: ESIClient, item_ids: list[int]) -> list[dict[str, Any]]:
    """Get names for a list of asset item IDs.

    Returns list of {item_id, name}.
    """
    if not item_ids:
        return []
    return client.post(
        f"/characters/{client.character_id}/assets/names/",
        json_data=item_ids,
    )


def get_asset_locations(client: ESIClient, item_ids: list[int]) -> list[dict[str, Any]]:
    """Get locations for a list of asset item IDs.

    Returns list of {item_id, position: {x, y, z}}.
    """
    if not item_ids:
        return []
    return client.post(
        f"/characters/{client.character_id}/assets/locations/",
        json_data=item_ids,
    )

