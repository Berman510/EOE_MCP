---
type: always
---

# EVE ESI Tool - Agent Guidelines

## Project Overview
This is a Python package that interfaces with the EVE Online ESI API via OAuth2 SSO. It exposes an MCP server (`mcp_server.py`) so an AI agent can query character data, assets, market prices, skills, fittings, and more. There is also a CLI (`cli.py`) for manual use.

## Key Files
- `mcp_server.py` - MCP server entry point; defines all tools exposed to the agent
- `cli.py` - Command-line interface for login and manual testing
- `config.yaml` - App credentials and ESI scopes (not committed; use `config.example.yaml` as template)
- `tokens.json` - Stored OAuth tokens (not committed)
- `eve_esi/` - Core library
  - `auth.py` - OAuth2 SSO flow and token storage
  - `client.py` - ESI HTTP client with auto token refresh
  - `config.py` - Config loading
  - `endpoints/` - ESI endpoint modules: `assets`, `characters`, `fitting_analysis`, `fittings`, `hauling`, `market`, `navigation`, `skills`, `universe`, `wallet`

## Scripts Folder
- All temporary or ad-hoc scripts must be saved to `scripts/` (e.g. `scripts/check_cargo.py`)
- Always clean up scripts from `scripts/` after use unless the user asks to keep them
- Never create temporary scripts in the workspace root

## Python Environment
- Run scripts with `python scripts/<filename>.py` from the workspace root
- Use whatever Python executable is available in the environment (`python` or `python3`)

## ESI API Patterns
- Use `client.get(path)` for authenticated requests, `client.get(path, authenticated=False)` for public endpoints
- NPC station IDs are in the `60000000-64000000` range; player structures are `> 1_000_000_000_000`
- Jita is in The Forge region (region_id: `10000002`)
- Blueprint `quantity == -1` means original (BPO); `quantity == -2` means copy (BPC)
- Asset `location_flag` values like `HiSlot*`, `MedSlot*`, `LoSlot*`, `Cargo`, `DroneBay` indicate fitted/carried items

## Code Style
- Use f-strings, type hints, and `from __future__ import annotations`
- Keep endpoint functions in `eve_esi/endpoints/` -- don't inline ESI calls into scripts or mcp_server.py
- All MCP tools return JSON strings (`json.dumps(data, indent=2)`)
- Prefer adding reusable functionality to endpoint modules rather than duplicating logic in scripts
