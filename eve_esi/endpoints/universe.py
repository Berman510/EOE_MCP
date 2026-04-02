"""Universe data endpoints (types, systems, etc.)."""

from __future__ import annotations

from typing import Any

from eve_esi.client import ESIClient


def get_type_info(client: ESIClient, type_id: int) -> dict[str, Any]:
    """Get information about an item type.

    Returns: name, description, group_id, market_group_id, volume, mass,
             dogma_attributes, dogma_effects, etc.
    """
    return client.get(f"/universe/types/{type_id}/", authenticated=False)


def get_group_info(client: ESIClient, group_id: int) -> dict[str, Any]:
    """Get information about an item group."""
    return client.get(f"/universe/groups/{group_id}/", authenticated=False)


def get_category_info(client: ESIClient, category_id: int) -> dict[str, Any]:
    """Get information about an item category."""
    return client.get(f"/universe/categories/{category_id}/", authenticated=False)


def get_system_info(client: ESIClient, system_id: int) -> dict[str, Any]:
    """Get information about a solar system."""
    return client.get(f"/universe/systems/{system_id}/", authenticated=False)


def get_station_info(client: ESIClient, station_id: int) -> dict[str, Any]:
    """Get information about a station."""
    return client.get(f"/universe/stations/{station_id}/", authenticated=False)


def get_structure_info(client: ESIClient, structure_id: int) -> dict[str, Any]:
    """Get information about a player-owned structure (requires auth)."""
    return client.get(f"/universe/structures/{structure_id}/")


def get_region_info(client: ESIClient, region_id: int) -> dict[str, Any]:
    """Get information about a region."""
    return client.get(f"/universe/regions/{region_id}/", authenticated=False)


def get_constellation_info(client: ESIClient, constellation_id: int) -> dict[str, Any]:
    """Get information about a constellation."""
    return client.get(f"/universe/constellations/{constellation_id}/", authenticated=False)


def resolve_ids(client: ESIClient, names: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Resolve names to IDs. Returns dict keyed by category (characters, corporations, etc.)."""
    if not names:
        return {}
    return client.post("/universe/ids/", json_data=names, authenticated=False)


def resolve_names(client: ESIClient, ids: list[int]) -> list[dict[str, Any]]:
    """Resolve IDs to names. Returns list of {id, name, category}.

    Automatically chunks into batches of 1000 (ESI limit).
    """
    if not ids:
        return []
    results: list[dict[str, Any]] = []
    unique = list(set(ids))
    for i in range(0, len(unique), 1000):
        chunk = unique[i:i + 1000]
        results.extend(client.post("/universe/names/", json_data=chunk, authenticated=False))
    return results


def get_route(
    client: ESIClient,
    origin: int,
    destination: int,
    flag: str = "shortest",
) -> list[int]:
    """Get a route between two solar systems.

    Args:
        origin: Origin solar system ID.
        destination: Destination solar system ID.
        flag: Route preference — 'shortest', 'secure', or 'insecure'.

    Returns:
        Ordered list of solar system IDs along the route (including origin
        and destination).
    """
    if origin == destination:
        return [origin]
    params: dict[str, Any] = {"flag": flag}
    return client.get(
        f"/route/{origin}/{destination}/",
        authenticated=False,
        params=params,
    )

