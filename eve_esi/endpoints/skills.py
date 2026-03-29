"""Skills and training queue endpoints."""

from __future__ import annotations

from typing import Any

from eve_esi.client import ESIClient


def get_skills(client: ESIClient) -> dict[str, Any]:
    """Get the skill list and total SP of the authenticated character.

    Returns dict with:
        - skills: list of {skill_id, active_skill_level, trained_skill_level, skillpoints_in_skill}
        - total_sp: total skillpoints
        - unallocated_sp: unallocated skillpoints
    """
    return client.get(f"/characters/{client.character_id}/skills/")


def get_skill_queue(client: ESIClient) -> list[dict[str, Any]]:
    """Get the current skill queue of the authenticated character.

    Returns list of skills in queue with:
        - skill_id, finished_level, queue_position
        - start_date, finish_date
        - training_start_sp, level_start_sp, level_end_sp
    """
    return client.get(f"/characters/{client.character_id}/skillqueue/")


def get_attributes(client: ESIClient) -> dict[str, Any]:
    """Get the character's attributes (intelligence, memory, etc.)."""
    return client.get(f"/characters/{client.character_id}/attributes/")


def get_clones(client: ESIClient) -> dict[str, Any]:
    """Get the character's clone information."""
    return client.get(f"/characters/{client.character_id}/clones/")


def get_implants(client: ESIClient) -> list[int]:
    """Get the character's active implant type IDs."""
    return client.get(f"/characters/{client.character_id}/implants/")

