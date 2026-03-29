"""MCP Server exposing EVE Online ESI tools for AI agent integration.

Run with:
    python mcp_server.py                   # stdio transport (default, for Claude Desktop / Augment)
    python mcp_server.py --transport sse    # SSE transport for web clients
"""

from __future__ import annotations

import json
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from eve_esi.config import AppConfig
from eve_esi.client import ESIClient
from eve_esi.endpoints import characters, skills, assets, wallet, fittings, market, universe

# Initialize MCP server
mcp = FastMCP(
    "EVE Online ESI",
    instructions=(
        "You are an EVE Online assistant with access to the ESI API. "
        "You can look up character information, skills, assets, wallet balances, "
        "market data, ship fittings, and more. Use these tools to help players "
        "optimize their gameplay, suggest ship fits, analyze market opportunities, "
        "and manage their EVE Online activities."
    ),
)

# Global client instance - lazily initialized
_config: AppConfig | None = None
_clients: dict[int, ESIClient] = {}


def _get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def _get_client(character_id: int | None = None) -> ESIClient:
    config = _get_config()
    if character_id is None:
        # Use first available character
        from eve_esi.auth import TokenStore
        store = TokenStore(config.token_storage.path)
        chars = store.get_all()
        if not chars:
            raise RuntimeError("No authenticated characters. Run `python cli.py login` first.")
        character_id = next(iter(chars))

    if character_id not in _clients:
        _clients[character_id] = ESIClient(config, character_id)
    return _clients[character_id]


# ──────────────────────────────────────────────
# Character Tools
# ──────────────────────────────────────────────

@mcp.tool()
def list_authenticated_characters() -> str:
    """List all EVE characters that have been authenticated with this tool."""
    config = _get_config()
    from eve_esi.auth import TokenStore
    store = TokenStore(config.token_storage.path)
    chars = store.get_all()
    if not chars:
        return "No authenticated characters. Run `python cli.py login` to add one."
    result = []
    for cid, token in chars.items():
        result.append({"character_id": cid, "character_name": token.character_name})
    return json.dumps(result, indent=2)


@mcp.tool()
def get_character_info(character_id: int | None = None) -> str:
    """Get public information about an EVE character including name, corp, birthday, etc.
    If character_id is not provided, uses the default authenticated character."""
    client = _get_client(character_id)
    cid = character_id or client.character_id
    info = characters.get_character_info(client, cid)
    return json.dumps(info, indent=2)


@mcp.tool()
def get_character_location(character_id: int | None = None) -> str:
    """Get the current in-game location of a character (system, station/structure)."""
    client = _get_client(character_id)
    location = characters.get_character_location(client)
    # Resolve system name
    if "solar_system_id" in location:
        try:
            sys_info = universe.get_system_info(client, location["solar_system_id"])
            location["solar_system_name"] = sys_info.get("name", "Unknown")
        except Exception:
            pass
    return json.dumps(location, indent=2)


@mcp.tool()
def get_character_ship(character_id: int | None = None) -> str:
    """Get the ship the character is currently flying."""
    client = _get_client(character_id)
    ship = characters.get_character_ship(client)
    # Resolve ship type name
    if "ship_type_id" in ship:
        try:
            type_info = universe.get_type_info(client, ship["ship_type_id"])
            ship["ship_type_name"] = type_info.get("name", "Unknown")
        except Exception:
            pass
    return json.dumps(ship, indent=2)


# ──────────────────────────────────────────────
# Skills Tools
# ──────────────────────────────────────────────

@mcp.tool()
def get_skills_summary(character_id: int | None = None) -> str:
    """Get a summary of the character's skills including total SP and skill list.
    Returns total_sp, unallocated_sp, and all trained skills with levels."""
    client = _get_client(character_id)
    data = skills.get_skills(client)
    return json.dumps(data, indent=2)


@mcp.tool()
def get_skill_queue(character_id: int | None = None) -> str:
    """Get the character's current skill training queue.
    Shows what skills are training and when they'll finish."""
    client = _get_client(character_id)
    queue = skills.get_skill_queue(client)
    # Resolve skill names
    skill_ids = list({s["skill_id"] for s in queue})
    if skill_ids:
        try:
            names = universe.resolve_names(client, skill_ids)
            name_map = {n["id"]: n["name"] for n in names}
            for entry in queue:
                entry["skill_name"] = name_map.get(entry["skill_id"], "Unknown")
        except Exception:
            pass
    return json.dumps(queue, indent=2)


@mcp.tool()
def get_character_attributes(character_id: int | None = None) -> str:
    """Get the character's attributes (intelligence, memory, perception, willpower, charisma)
    and any active neural remaps."""
    client = _get_client(character_id)
    attrs = skills.get_attributes(client)
    return json.dumps(attrs, indent=2)


@mcp.tool()
def get_active_implants(character_id: int | None = None) -> str:
    """Get the character's currently active implants."""
    client = _get_client(character_id)
    implant_ids = skills.get_implants(client)
    result = []
    for imp_id in implant_ids:
        try:
            info = universe.get_type_info(client, imp_id)
            result.append({"type_id": imp_id, "name": info.get("name", "Unknown")})
        except Exception:
            result.append({"type_id": imp_id, "name": "Unknown"})
    return json.dumps(result, indent=2)


# ──────────────────────────────────────────────
# Assets Tools
# ──────────────────────────────────────────────

@mcp.tool()
def get_assets_list(character_id: int | None = None) -> str:
    """Get all assets owned by the character. Returns item IDs, type IDs,
    locations, quantities. Can be a large list for veteran characters."""
    client = _get_client(character_id)
    items = assets.get_assets(client)
    # Resolve type names for the first 100 unique types
    type_ids = list({i["type_id"] for i in items})[:100]
    if type_ids:
        try:
            names = universe.resolve_names(client, type_ids)
            name_map = {n["id"]: n["name"] for n in names}
            for item in items:
                if item["type_id"] in name_map:
                    item["type_name"] = name_map[item["type_id"]]
        except Exception:
            pass
    return json.dumps(items, indent=2)


@mcp.tool()
def search_assets(
    type_name: str,
    character_id: int | None = None,
) -> str:
    """Search character assets by item type name. More targeted than get_assets_list."""
    client = _get_client(character_id)
    # First resolve the name to type IDs
    id_results = universe.resolve_ids(client, [type_name])
    target_type_ids = set()
    for category in id_results.values():
        if isinstance(category, list):
            for item in category:
                if isinstance(item, dict) and "id" in item:
                    target_type_ids.add(item["id"])

    if not target_type_ids:
        return json.dumps({"error": f"No types found matching '{type_name}'"})

    all_assets = assets.get_assets(client)
    matching = [a for a in all_assets if a["type_id"] in target_type_ids]

    # Resolve names
    type_ids = list({i["type_id"] for i in matching})
    if type_ids:
        try:
            names = universe.resolve_names(client, type_ids)
            name_map = {n["id"]: n["name"] for n in names}
            for item in matching:
                item["type_name"] = name_map.get(item["type_id"], "Unknown")
        except Exception:
            pass

    return json.dumps(matching, indent=2)


# ──────────────────────────────────────────────
# Wallet Tools
# ──────────────────────────────────────────────

@mcp.tool()
def get_wallet_balance(character_id: int | None = None) -> str:
    """Get the character's current ISK wallet balance."""
    client = _get_client(character_id)
    balance = wallet.get_wallet_balance(client)
    return json.dumps({"balance_isk": balance}, indent=2)


@mcp.tool()
def get_wallet_journal(character_id: int | None = None) -> str:
    """Get the character's wallet journal (recent financial transactions)."""
    client = _get_client(character_id)
    journal = wallet.get_wallet_journal(client)
    return json.dumps(journal, indent=2)


# ──────────────────────────────────────────────
# Fittings Tools
# ──────────────────────────────────────────────

@mcp.tool()
def get_ship_fittings(character_id: int | None = None) -> str:
    """Get all saved ship fittings for the character."""
    client = _get_client(character_id)
    fits = fittings.get_fittings(client)
    # Resolve ship type names
    ship_type_ids = list({f["ship_type_id"] for f in fits})
    if ship_type_ids:
        try:
            names = universe.resolve_names(client, ship_type_ids)
            name_map = {n["id"]: n["name"] for n in names}
            for fit in fits:
                fit["ship_type_name"] = name_map.get(fit["ship_type_id"], "Unknown")
        except Exception:
            pass
    return json.dumps(fits, indent=2)


@mcp.tool()
def save_ship_fitting(
    name: str,
    description: str,
    ship_type_id: int,
    items: list[dict[str, Any]],
    character_id: int | None = None,
) -> str:
    """Save a new ship fitting to the character's fitting list.

    Args:
        name: Fitting name
        description: Fitting description
        ship_type_id: Type ID of the ship hull
        items: List of modules, each with {type_id, flag, quantity}.
            flag examples: HiSlot0-7, MedSlot0-7, LoSlot0-7, RigSlot0-2,
                          SubSystemSlot0-3, DroneBay, FighterBay, Cargo
    """
    client = _get_client(character_id)
    result = fittings.create_fitting(client, name, description, ship_type_id, items)
    return json.dumps(result, indent=2)


# ──────────────────────────────────────────────
# Market Tools
# ──────────────────────────────────────────────

@mcp.tool()
def get_market_orders(character_id: int | None = None) -> str:
    """Get the character's active market orders."""
    client = _get_client(character_id)
    orders = market.get_character_orders(client)
    return json.dumps(orders, indent=2)


@mcp.tool()
def check_item_price(
    type_id: int,
    region_id: int = 10000002,
) -> str:
    """Check market prices for an item in a region.
    Default region is The Forge (Jita). Returns buy and sell orders.

    Common region IDs:
        10000002 = The Forge (Jita)
        10000043 = Domain (Amarr)
        10000032 = Sinq Laison (Dodixie)
        10000042 = Metropolis (Hek)
        10000030 = Heimatar (Rens)
    """
    client = _get_client()
    orders = market.get_market_orders_region(client, region_id, type_id)

    buy_orders = [o for o in orders if o.get("is_buy_order")]
    sell_orders = [o for o in orders if not o.get("is_buy_order")]

    buy_orders.sort(key=lambda o: o["price"], reverse=True)
    sell_orders.sort(key=lambda o: o["price"])

    result = {
        "type_id": type_id,
        "region_id": region_id,
        "best_buy_price": buy_orders[0]["price"] if buy_orders else None,
        "best_sell_price": sell_orders[0]["price"] if sell_orders else None,
        "total_buy_volume": sum(o["volume_remain"] for o in buy_orders),
        "total_sell_volume": sum(o["volume_remain"] for o in sell_orders),
        "top_5_buy_orders": buy_orders[:5],
        "top_5_sell_orders": sell_orders[:5],
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def get_blueprints_list(character_id: int | None = None) -> str:
    """Get all blueprints owned by the character with ME/TE/runs info."""
    client = _get_client(character_id)
    bps = market.get_blueprints(client)
    type_ids = list({b["type_id"] for b in bps})[:100]
    if type_ids:
        try:
            names = universe.resolve_names(client, type_ids)
            name_map = {n["id"]: n["name"] for n in names}
            for bp in bps:
                if bp["type_id"] in name_map:
                    bp["type_name"] = name_map[bp["type_id"]]
        except Exception:
            pass
    return json.dumps(bps, indent=2)


@mcp.tool()
def get_industry_jobs_list(
    include_completed: bool = False,
    character_id: int | None = None,
) -> str:
    """Get the character's industry jobs (manufacturing, research, etc.)."""
    client = _get_client(character_id)
    jobs = market.get_industry_jobs(client, include_completed)
    return json.dumps(jobs, indent=2)


# ──────────────────────────────────────────────
# Universe / Lookup Tools
# ──────────────────────────────────────────────

@mcp.tool()
def lookup_item_type(type_id: int) -> str:
    """Look up detailed information about an EVE item type by its type ID.
    Returns name, description, attributes, group, etc."""
    client = _get_client()
    info = universe.get_type_info(client, type_id)
    return json.dumps(info, indent=2)


@mcp.tool()
def search_item_type(name: str) -> str:
    """Search for an EVE item type by name. Returns matching type IDs and names."""
    client = _get_client()
    results = universe.resolve_ids(client, [name])
    return json.dumps(results, indent=2)


@mcp.tool()
def lookup_solar_system(system_id: int) -> str:
    """Look up information about a solar system by its ID."""
    client = _get_client()
    info = universe.get_system_info(client, system_id)
    return json.dumps(info, indent=2)


@mcp.tool()
def resolve_eve_names(ids: list[int]) -> str:
    """Resolve EVE IDs to names. Works for characters, corporations, alliances,
    types, systems, stations, etc."""
    client = _get_client()
    names = universe.resolve_names(client, ids)
    return json.dumps(names, indent=2)


# ──────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────

def main():
    """Run the MCP server."""
    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    if transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

