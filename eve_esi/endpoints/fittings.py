"""Ship fitting endpoints."""

from __future__ import annotations

from typing import Any

from eve_esi.client import ESIClient


def get_fittings(client: ESIClient) -> list[dict[str, Any]]:
    """Get all saved ship fittings of the authenticated character.

    Returns list of fittings with:
        - fitting_id, name, description, ship_type_id
        - items: list of {type_id, flag, quantity}
    """
    return client.get(f"/characters/{client.character_id}/fittings/")


def create_fitting(
    client: ESIClient,
    name: str,
    description: str,
    ship_type_id: int,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a new ship fitting.

    Args:
        name: Fitting name
        description: Fitting description
        ship_type_id: Type ID of the ship hull
        items: List of {type_id: int, flag: str, quantity: int}
            flag values: HiSlot0-7, MedSlot0-7, LoSlot0-7, RigSlot0-2,
                        SubSystemSlot0-3, DroneBay, FighterBay, Cargo

    Returns:
        {fitting_id: int} of the newly created fitting
    """
    fitting_data = {
        "name": name,
        "description": description,
        "ship_type_id": ship_type_id,
        "items": items,
    }
    return client.post(
        f"/characters/{client.character_id}/fittings/",
        json_data=fitting_data,
    )


def delete_fitting(client: ESIClient, fitting_id: int) -> None:
    """Delete a ship fitting."""
    client.delete(f"/characters/{client.character_id}/fittings/{fitting_id}/")

