"""Character information endpoints."""

from __future__ import annotations

from typing import Any

from eve_esi.client import ESIClient


def get_character_info(client: ESIClient, character_id: int | None = None) -> dict[str, Any]:
    """Get public information about a character."""
    cid = character_id or client.character_id
    return client.get(f"/characters/{cid}/", authenticated=False)


def get_character_portrait(client: ESIClient, character_id: int | None = None) -> dict[str, Any]:
    """Get portrait URLs for a character."""
    cid = character_id or client.character_id
    return client.get(f"/characters/{cid}/portrait/", authenticated=False)


def get_character_location(client: ESIClient) -> dict[str, Any]:
    """Get the current location of the authenticated character."""
    return client.get(f"/characters/{client.character_id}/location/")


def get_character_ship(client: ESIClient) -> dict[str, Any]:
    """Get the current ship type of the authenticated character."""
    return client.get(f"/characters/{client.character_id}/ship/")


def get_character_online(client: ESIClient) -> dict[str, Any]:
    """Get online status of the authenticated character."""
    return client.get(f"/characters/{client.character_id}/online/")


def get_corporation_info(client: ESIClient, corporation_id: int) -> dict[str, Any]:
    """Get public information about a corporation."""
    return client.get(f"/corporations/{corporation_id}/", authenticated=False)


def get_alliance_info(client: ESIClient, alliance_id: int) -> dict[str, Any]:
    """Get public information about an alliance."""
    return client.get(f"/alliances/{alliance_id}/", authenticated=False)


def resolve_names(client: ESIClient, ids: list[int]) -> list[dict[str, Any]]:
    """Resolve a list of IDs to names (characters, corps, alliances, types, etc.)."""
    if not ids:
        return []
    return client.post("/universe/names/", json_data=ids, authenticated=False)


def search_characters(client: ESIClient, name: str) -> dict[str, Any]:
    """Search for characters by name."""
    return client.get("/characters/0/search/", params={"search": name, "categories": "character"})

