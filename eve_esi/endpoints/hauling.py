"""Asset analysis and haul-planning utilities."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from eve_esi.client import ESIClient
from eve_esi.endpoints import assets as assets_ep, market as market_ep, universe
from eve_esi.endpoints import navigation


# ── Location helpers ──────────────────────────────────────────────────────────

def _resolve_locations(
    client: ESIClient,
    location_ids: set[int],
) -> dict[int, dict[str, Any]]:
    """Resolve station / structure IDs to {name, system_id}."""
    info: dict[int, dict[str, Any]] = {}
    for lid in location_ids:
        if 60_000_000 <= lid <= 64_000_000:
            try:
                s = universe.get_station_info(client, lid)
                info[lid] = {"name": s["name"], "system_id": s["system_id"]}
            except Exception:
                info[lid] = {"name": f"Station {lid}", "system_id": None}
        elif lid > 1_000_000_000_000:
            try:
                s = universe.get_structure_info(client, lid)
                info[lid] = {"name": s["name"], "system_id": s.get("solar_system_id")}
            except Exception:
                info[lid] = {"name": f"Structure {lid}", "system_id": None}
    return info


# ── Assets summary ────────────────────────────────────────────────────────────

def get_assets_summary_by_location(
    client: ESIClient,
) -> list[dict[str, Any]]:
    """Group all hangar assets by location with names and estimated values.

    Returns list of locations, each with items, total value, total volume.
    """
    all_assets = assets_ep.get_assets(client)
    hangar = [a for a in all_assets if a.get("location_flag") == "Hangar"]

    # Resolve locations
    loc_ids = {a["location_id"] for a in hangar}
    loc_info = _resolve_locations(client, loc_ids)

    # Market prices
    prices_raw = market_ep.get_market_prices(client)
    price_map = {p["type_id"]: p.get("adjusted_price") or p.get("average_price") or 0
                 for p in prices_raw}

    # Resolve type names (batch)
    type_ids = list({a["type_id"] for a in hangar})
    name_map: dict[int, str] = {}
    try:
        resolved = universe.resolve_names(client, type_ids)
        for r in resolved:
            name_map[r["id"]] = r["name"]
    except Exception:
        pass

    # Group
    by_loc: dict[int, list[dict]] = defaultdict(list)
    for a in hangar:
        qty = max(a.get("quantity", 1), 1)
        val = price_map.get(a["type_id"], 0) * qty
        by_loc[a["location_id"]].append({
            "type_id": a["type_id"],
            "type_name": name_map.get(a["type_id"], f"Type {a['type_id']}"),
            "quantity": qty,
            "estimated_value": round(val, 2),
        })

    results: list[dict[str, Any]] = []
    for lid, items in by_loc.items():
        li = loc_info.get(lid, {})
        total_val = sum(i["estimated_value"] for i in items)
        results.append({
            "location_id": lid,
            "location_name": li.get("name", f"Location {lid}"),
            "system_id": li.get("system_id"),
            "items": sorted(items, key=lambda x: -x["estimated_value"]),
            "total_estimated_value": round(total_val, 2),
            "item_count": len(items),
        })
    results.sort(key=lambda x: -x["total_estimated_value"])
    return results



# ── Haul planner ──────────────────────────────────────────────────────────────

def find_portable_valuables(
    client: ESIClient,
    *,
    exclude_system: int = 30000142,
    max_cargo_m3: float = 135.0,
    min_value_isk: float = 500_000,
    max_unit_volume: float = 10.0,
    include_blueprints: bool = True,
    route_flag: str = "shortest",
) -> dict[str, Any]:
    """Find valuable, small items outside a home system and plan a pickup route.

    Args:
        exclude_system: System to exclude (default: Jita 30000142).
        max_cargo_m3: Available cargo volume (e.g. 135 m3 for an Ares).
        min_value_isk: Minimum adjusted-price value to consider (non-BPs).
        max_unit_volume: Max unit volume for non-BP items.
        include_blueprints: Whether to include blueprints (always tiny volume).
        route_flag: 'shortest', 'secure', or 'insecure'.

    Returns dict with selected_items, route, cargo stats, and leftovers.
    """
    # ── Data collection ───────────────────────────────────────────────────
    all_assets = assets_ep.get_assets(client)
    blueprints = market_ep.get_blueprints(client)
    bp_item_ids = {b["item_id"] for b in blueprints}

    prices_raw = market_ep.get_market_prices(client)
    price_map = {p["type_id"]: p.get("adjusted_price") or p.get("average_price") or 0
                 for p in prices_raw}

    hangar = [a for a in all_assets if a.get("location_flag") == "Hangar"]
    bp_locs = {b["location_id"] for b in blueprints if b.get("location_flag") == "Hangar"}
    all_loc_ids = {a["location_id"] for a in hangar} | bp_locs
    loc_info = _resolve_locations(client, all_loc_ids)

    def _sys(lid: int) -> int | None:
        return loc_info.get(lid, {}).get("system_id")

    # ── Blueprint candidates ──────────────────────────────────────────────
    candidates: list[dict[str, Any]] = []
    if include_blueprints:
        for b in blueprints:
            if _sys(b["location_id"]) in (exclude_system, None):
                continue
            if b.get("location_flag", "Hangar") != "Hangar":
                continue
            qty = b.get("quantity", 1)
            adj = price_map.get(b["type_id"], 0) * max(qty, 1)
            candidates.append({
                "item_id": b["item_id"], "type_id": b["type_id"],
                "location_id": b["location_id"],
                "is_blueprint": True,
                "quantity": qty, "qty": max(qty, 1),
                "bp_type": "BPO" if qty == -1 else ("BPC" if qty == -2 else "stack"),
                "me": b.get("material_efficiency", 0),
                "te": b.get("time_efficiency", 0),
                "runs": b.get("runs", -1),
                "estimated_value": adj,
                "unit_volume": 0.01, "stack_volume": 0.01 * max(qty, 1),
                "type_name": "",
            })

    # ── Non-BP candidates ─────────────────────────────────────────────────
    nonbp: list[dict[str, Any]] = []
    for a in hangar:
        if a["item_id"] in bp_item_ids:
            continue
        if _sys(a["location_id"]) in (exclude_system, None):
            continue
        qty = max(a.get("quantity", 1), 1)
        adj = price_map.get(a["type_id"], 0) * qty
        if adj < min_value_isk:
            continue
        nonbp.append({
            "item_id": a["item_id"], "type_id": a["type_id"],
            "location_id": a["location_id"],
            "is_blueprint": False,
            "quantity": a.get("quantity", 1), "qty": qty,
            "estimated_value": adj,
            "type_name": "",
        })

    # ── Resolve names (batch) ─────────────────────────────────────────────
    all_type_ids = list({c["type_id"] for c in candidates + nonbp})
    name_map: dict[int, str] = {}
    try:
        resolved = universe.resolve_names(client, all_type_ids)
        for r in resolved:
            name_map[r["id"]] = r["name"]
    except Exception:
        pass
    for c in candidates:
        c["type_name"] = name_map.get(c["type_id"], f"Type {c['type_id']}")

    # ── Fetch volumes for non-BP types ────────────────────────────────────
    nonbp_tids = list({c["type_id"] for c in nonbp})
    vol_map: dict[int, float] = {}
    for tid in nonbp_tids:
        try:
            info = universe.get_type_info(client, tid)
            vol_map[tid] = info.get("packaged_volume") or info.get("volume") or 1.0
        except Exception:
            vol_map[tid] = 1.0

    for c in nonbp:
        c["type_name"] = name_map.get(c["type_id"], f"Type {c['type_id']}")
        c["unit_volume"] = vol_map.get(c["type_id"], 1.0)
        c["stack_volume"] = c["unit_volume"] * c["qty"]

    # Drop bulky
    nonbp = [c for c in nonbp if c["unit_volume"] <= max_unit_volume]

    # ── Merge, sort, greedy-pack ──────────────────────────────────────────
    all_cands = candidates + nonbp
    all_cands.sort(key=lambda x: (not x["is_blueprint"],
                                   -(x["estimated_value"] / max(x["stack_volume"], 0.001))))

    selected: list[dict[str, Any]] = []
    used_m3 = 0.0
    for c in all_cands:
        sv = c["stack_volume"]
        if used_m3 + sv <= max_cargo_m3:
            selected.append(c)
            used_m3 += sv

    # ── Route ─────────────────────────────────────────────────────────────
    sel_systems = list({_sys(c["location_id"]) for c in selected} - {None})
    route_result = navigation.plan_multi_stop_route(
        client, sel_systems, start=exclude_system, end=exclude_system, flag=route_flag,
    )

    # ── Enrich selected items with location names ─────────────────────────
    for c in selected:
        li = loc_info.get(c["location_id"], {})
        c["location_name"] = li.get("name", f"Location {c['location_id']}")
        c["system_id"] = li.get("system_id")

    left = [c for c in all_cands if c not in selected]

    return {
        "selected_items": selected,
        "route": route_result,
        "cargo_used_m3": round(used_m3, 2),
        "cargo_max_m3": max_cargo_m3,
        "total_estimated_value": round(sum(c["estimated_value"] for c in selected), 2),
        "items_left_behind": len(left),
        "value_left_behind": round(sum(c["estimated_value"] for c in left), 2),
    }