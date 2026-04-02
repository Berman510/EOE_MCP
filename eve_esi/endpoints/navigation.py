"""Navigation and route-planning utilities."""

from __future__ import annotations

from typing import Any

from eve_esi.client import ESIClient
from eve_esi.endpoints import universe


def get_jump_count(
    client: ESIClient,
    origin: int,
    destination: int,
    flag: str = "shortest",
) -> int:
    """Return the number of jumps between two systems.

    Args:
        origin: Origin solar system ID.
        destination: Destination solar system ID.
        flag: 'shortest', 'secure', or 'insecure'.
    """
    route = universe.get_route(client, origin, destination, flag=flag)
    return max(len(route) - 1, 0)


def plan_multi_stop_route(
    client: ESIClient,
    systems: list[int],
    start: int,
    end: int | None = None,
    flag: str = "shortest",
) -> dict[str, Any]:
    """Plan an efficient multi-stop route using nearest-neighbour heuristic.

    Args:
        systems: List of solar system IDs to visit.
        start: Starting solar system ID.
        end: System to return to at the end (defaults to *start*).
        flag: Route preference — 'shortest', 'secure', or 'insecure'.

    Returns:
        {
            "route": [{"system_id", "system_name", "jumps_from_previous"}],
            "total_jumps": int,
            "systems_visited": int,
        }
    """
    if end is None:
        end = start

    # De-duplicate, drop start/end from the list
    to_visit = list({s for s in systems if s not in (start, end)})

    # Cache jump counts
    _cache: dict[tuple[int, int], int] = {}

    def _jumps(a: int, b: int) -> int:
        if a == b:
            return 0
        key = (min(a, b), max(a, b))
        if key not in _cache:
            _cache[key] = get_jump_count(client, a, b, flag=flag)
        return _cache[key]

    # Nearest-neighbour TSP
    order: list[int] = []
    current = start
    remaining = to_visit[:]
    while remaining:
        nxt = min(remaining, key=lambda s: _jumps(current, s))
        order.append(nxt)
        remaining.remove(nxt)
        current = nxt

    # Resolve system names in one batch
    all_ids = list({start, end} | set(order))
    name_map: dict[int, str] = {}
    try:
        resolved = universe.resolve_names(client, all_ids)
        for r in resolved:
            name_map[r["id"]] = r["name"]
    except Exception:
        pass

    # Build result
    route_entries: list[dict[str, Any]] = []
    prev = start
    total_jumps = 0
    for sys_id in order:
        j = _jumps(prev, sys_id)
        total_jumps += j
        route_entries.append({
            "system_id": sys_id,
            "system_name": name_map.get(sys_id, f"System {sys_id}"),
            "jumps_from_previous": j,
        })
        prev = sys_id

    # Return leg
    ret_jumps = _jumps(prev, end)
    total_jumps += ret_jumps
    route_entries.append({
        "system_id": end,
        "system_name": name_map.get(end, f"System {end}"),
        "jumps_from_previous": ret_jumps,
        "is_return": True,
    })

    return {
        "start": {"system_id": start, "system_name": name_map.get(start, f"System {start}")},
        "route": route_entries,
        "total_jumps": total_jumps,
        "systems_visited": len(order),
    }

