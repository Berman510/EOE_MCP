# EVE ESI Tool 🚀

An EVE Online ESI API interface with a **Model Context Protocol (MCP) server** for AI agent integration. Connect your EVE character to Claude, Augment Code, Cursor, or any MCP-compatible AI assistant — then ask questions like *"What's in my cargo hold?"*, *"Suggest a Hookbill fit for solo FW"*, or *"What are my most valuable assets?"*

---

## Architecture

```mermaid
graph TB
    subgraph AI["AI Clients"]
        A[Claude Desktop]
        B[Augment Code]
        C[Cursor]
        D[Claude Code CLI]
    end

    subgraph MCP["MCP Server · mcp_server.py"]
        E["34 Tools\n──────────────────\nCharacter · Skills · Assets\nWallet · Fittings · Market\nUniverse · Navigation\nHauling · Fitting Analysis\nCross-Character"]
    end

    subgraph LIB["eve_esi library"]
        F["auth.py\nOAuth2 SSO + PKCE"]
        G["client.py\nESI HTTP Client\nauto token refresh"]
        H["endpoints/\nassets · characters · fittings\nfitting_analysis · hauling · market\nnavigation · skills · universe · wallet"]
    end

    subgraph EVE["EVE Online"]
        I["ESI API\nesi.evetech.net"]
        J["SSO\nlogin.eveonline.com"]
    end

    A & B & C & D -->|"stdio / MCP protocol"| E
    E --> G
    G --> H
    F -->|"tokens.json"| G
    G -->|"HTTPS + JWT Bearer"| I
    F -->|"PKCE / Auth Code flow"| J
```

## OAuth2 Authentication Flow

```mermaid
sequenceDiagram
    participant U as You
    participant CLI as cli.py
    participant Browser as Browser
    participant SSO as EVE SSO
    participant ESI as ESI API

    U->>CLI: python cli.py login
    CLI->>Browser: Open auth URL (PKCE challenge)
    Browser->>SSO: EVE login + scope approval
    SSO->>CLI: Redirect → localhost:8182/callback?code=...
    CLI->>SSO: POST /token (exchange code)
    SSO->>CLI: access_token + refresh_token
    CLI->>CLI: Store encrypted in tokens.json
    Note over CLI,ESI: All future requests auto-refresh token
    CLI->>ESI: GET /characters/{id}/
    ESI->>CLI: Character data ✓
```

---

## Prerequisites

- **Python 3.11+**
- **An EVE Online account**
- **A registered EVE developer application** (free — takes 2 minutes at [developers.eveonline.com](https://developers.eveonline.com/))

---

## Installation

```bash
git clone https://github.com/yourname/eve-esi-tool
cd eve-esi-tool
pip install -e .
```

---

## Step 1 — Register an EVE Application

1. Go to [developers.eveonline.com](https://developers.eveonline.com/) → sign in → **Applications → Create Application**
2. Set **Connection Type** → `Authentication & API Access`
3. Set **Callback URL** → `http://localhost:8182/callback`
4. Add whichever ESI scopes you want (see [Scopes Reference](#scopes-reference) below)
5. Copy your **Client ID** and optionally **Client Secret**

> **PKCE vs Secret:** If you omit `client_secret` from `config.yaml`, the tool uses PKCE (safer for desktop apps). If you include it, it uses the standard Authorization Code flow with Basic Auth.

---

## Step 2 — Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:

```yaml
eve_sso:
  client_id: "YOUR_CLIENT_ID_HERE"
  client_secret: "YOUR_SECRET_HERE"   # optional — remove for PKCE-only
  callback_url: "http://localhost:8182/callback"
  scopes:
    - "esi-skills.read_skills.v1"
    - "esi-skills.read_skillqueue.v1"
    - "esi-characters.read_blueprints.v1"
    - "esi-assets.read_assets.v1"
    - "esi-wallet.read_character_wallet.v1"
    - "esi-fittings.read_fittings.v1"
    - "esi-fittings.write_fittings.v1"
    - "esi-markets.read_character_orders.v1"
    - "esi-industry.read_character_jobs.v1"
    - "esi-location.read_location.v1"
    - "esi-location.read_ship_type.v1"
    - "esi-clones.read_clones.v1"
    - "esi-clones.read_implants.v1"
    - "esi-contracts.read_character_contracts.v1"
    - "esi-universe.read_structures.v1"

token_storage:
  path: "tokens.json"
```

---

## Step 3 — Log In

```bash
python cli.py login
```

A browser window opens for EVE SSO. After you approve, your tokens are saved to `tokens.json`. **Run this once per character.** You can authenticate multiple characters — all tools accept an optional `character_id` parameter.

---

## CLI Reference

```bash
python cli.py login    # Authenticate a character via EVE SSO
python cli.py chars    # List all authenticated characters
python cli.py info     # Show character info (corp, alliance, etc.)
python cli.py skills   # Show skill summary (total SP, top skills)
python cli.py wallet   # Show ISK wallet balance
python cli.py queue    # Show skill training queue
```

---

## Step 4 — Connect to Your AI Tool

The MCP server uses **stdio transport** — the AI client launches it as a subprocess and communicates over stdin/stdout.

### Augment Code (VS Code)

Open your VS Code user settings (Ctrl+Shift+P → **"Preferences: Open User Settings (JSON)"**) and add:

```json
{
  "augment.advanced": {
    "mcpServers": {
      "eve-esi": {
        "command": "python",
        "args": ["C:/path/to/eve-esi-tool/mcp_server.py"],
        "cwd": "C:/path/to/eve-esi-tool"
      }
    }
  }
}
```

Then reload VS Code (Ctrl+Shift+P → **"Developer: Reload Window"**). The EVE ESI tools will be available in Agent mode automatically.

> **Windows tip:** Use forward slashes `/` or double backslashes `\\` in the path.

---

### Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` on Windows, or `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS. Create the file if it doesn't exist:

```json
{
  "mcpServers": {
    "eve-esi": {
      "command": "python",
      "args": ["/path/to/eve-esi-tool/mcp_server.py"],
      "cwd": "/path/to/eve-esi-tool"
    }
  }
}
```

Restart Claude Desktop. You'll see a **🔨 hammer icon** in the chat input bar when MCP tools are loaded. Click it to see all available tools.

> **Enable developer mode:** In Claude Desktop → Settings → Developer → Enable Developer Mode to see the config file path for your OS.

---

### Cursor

Add to `.cursor/mcp.json` in your project root, or `~/.cursor/mcp.json` globally:

```json
{
  "mcpServers": {
    "eve-esi": {
      "command": "python",
      "args": ["/path/to/eve-esi-tool/mcp_server.py"],
      "cwd": "/path/to/eve-esi-tool"
    }
  }
}
```

Enable MCP in **Cursor Settings → Features → MCP → Enable MCP**.

---

### Claude Code (CLI)

```bash
# Add the server
claude mcp add eve-esi python /path/to/eve-esi-tool/mcp_server.py

# Or add with working directory
claude mcp add eve-esi --cwd /path/to/eve-esi-tool python mcp_server.py

# Verify it's registered
claude mcp list
```

---

## Available MCP Tools

```mermaid
mindmap
  root((EVE ESI\nMCP Tools))
    Character
      list_authenticated_characters
      set_active_character
      get_character_info
      get_character_location
      get_character_ship
      get_character_status
    Skills
      get_skills_summary
      get_skill_queue
      get_character_attributes
      get_active_implants
    Assets
      get_assets_list
      search_assets
      get_assets_summary
    Wallet
      get_wallet_balance
      get_wallet_journal
    Fittings
      get_ship_fittings
      save_ship_fitting
    Market
      get_market_orders
      check_item_price
      get_blueprints_list
      get_industry_jobs_list
    Universe
      lookup_item_type
      search_item_type
      lookup_solar_system
      resolve_eve_names
    Navigation
      plan_route
    Hauling
      find_valuables_to_haul
    Fitting Analysis
      get_ship_fit_stats
      compare_ship_fits
      get_fit_required_skills
      check_fit_readiness
    Cross-Character
      get_all_characters_status
      compare_skills_across_characters
      compare_wallets
```

### Character & Status

| Tool | Description |
|---|---|
| `list_authenticated_characters` | List all characters with location, ship, wallet, and active status |
| `set_active_character` | Set which character tools default to when `character_id` is omitted |
| `get_character_info` | Name, corp, alliance, birthday, security status |
| `get_character_location` | Current solar system |
| `get_character_ship` | Ship currently flying |
| `get_character_status` | One-call snapshot: location + ship + wallet balance |

### Skills

| Tool | Description |
|---|---|
| `get_skills_summary` | Total SP, unallocated SP, all trained skills |
| `get_skill_queue` | Skills in queue with finish times |
| `get_character_attributes` | Int/Mem/Per/Wil/Cha + remap availability |
| `get_active_implants` | Implants currently plugged in |

### Assets & Wallet

| Tool | Description |
|---|---|
| `get_assets_list` | All owned items with location/quantity |
| `search_assets` | Search assets by item type name |
| `get_assets_summary` | Assets grouped by station with ISK values |
| `get_wallet_balance` | ISK balance |
| `get_wallet_journal` | Recent wallet transactions |

### Fittings & Market

| Tool | Description |
|---|---|
| `get_ship_fittings` | All saved fittings in-game |
| `save_ship_fitting` | Save a new fitting to the game ✍️ |
| `get_market_orders` | Character's active sell/buy orders |
| `check_item_price` | Best buy/sell prices in any region (default: Jita) |
| `get_blueprints_list` | All blueprints with ME/TE/runs info |
| `get_industry_jobs_list` | Active/completed manufacturing & research jobs |

### Universe & Navigation

| Tool | Description |
|---|---|
| `lookup_item_type` | Full type info + dogma attributes for any item ID |
| `search_item_type` | Find item IDs by name |
| `lookup_solar_system` | System info (security, planets, stargates) |
| `resolve_eve_names` | Convert any EVE IDs → names |
| `plan_route` | Multi-system route planner with nearest-neighbour optimization |

### Hauling

| Tool | Description |
|---|---|
| `find_valuables_to_haul` | Scan assets for small/valuable items, plan pickup route with pricing |

### Fitting Analysis

| Tool | Description |
|---|---|
| `get_ship_fit_stats` | Parse an EFT fit → full stats (defense, fitting, nav, cap, mining, cargo) |
| `compare_ship_fits` | Side-by-side comparison of two EFT fits with deltas |
| `get_fit_required_skills` | Extract all skills required to fly a given EFT fit |
| `check_fit_readiness` | Check which characters can fly a fit and what skills they're missing |

### Cross-Character

| Tool | Description |
|---|---|
| `get_all_characters_status` | Location, ship, and wallet for ALL authenticated characters |
| `compare_skills_across_characters` | Compare specific skills (or total SP) across all characters |
| `compare_wallets` | All wallet balances + total ISK across accounts |

> ✍️ `save_ship_fitting` is the only tool that **writes** to your account. All others are read-only.

---

## Example Conversations

Once connected, you can ask natural language questions:

```
"What ship is my character flying and where are they?"
"Show me my top 10 most valuable assets"
"What skills am I training and when does the queue finish?"
"Check the Jita price for a Raven Navy Issue"
"Do I have any active industry jobs?"
"What are my saved fittings for a Rifter?"
"Suggest a solo PvP fit for my Caldari Navy Hookbill based on my skills"
"How much would I make if I sold all my blueprints in Jita?"
"Compare my Covetor fit to a Hulk fit — which is better for moon mining?"
"What skills do I need to fly this Hulk fit?" (paste EFT)
"Which of my characters can fly this fit and what are they missing?"
"Give me a status update on all my characters"
"Compare Mining Barge and Astrogeology skills across all my alts"
"Find all my valuable items scattered around and plan a pickup route back to Jita"
```

---

## Multi-Character Support

You can authenticate multiple EVE characters. Run `python cli.py login` once per character — all tokens are stored in `tokens.json`.

```bash
# Log in additional characters (run once per character)
python cli.py login

# List all authenticated characters
python cli.py chars
```

### Active Character

Use `set_active_character` to choose which character tools default to when `character_id` is omitted. If no active character is set, the first authenticated character is used.

All individual tools also accept an optional `character_id` parameter for ad-hoc queries on a specific alt.

### Cross-Character Tools

These tools operate on **all** authenticated characters at once — no need to query them one by one:

- **`get_all_characters_status`** — Location, ship, and wallet for everyone in one call
- **`compare_skills_across_characters`** — Compare specific skills or total SP side-by-side
- **`compare_wallets`** — All wallet balances + fleet total ISK
- **`check_fit_readiness`** — Check which characters can fly a given fit and what they're missing

---

## Project Structure

```
eve-esi-tool/
├── mcp_server.py          # MCP server — 34 tools for AI agents
├── cli.py                 # Command-line interface
├── config.example.yaml    # Config template
├── config.yaml            # Your config (not committed)
├── tokens.json            # OAuth tokens (not committed)
├── scripts/               # Temporary/ad-hoc scripts (auto-cleaned)
├── eve_esi/
│   ├── auth.py            # OAuth2 SSO + PKCE flow + token storage
│   ├── client.py          # ESI HTTP client with auto token refresh
│   ├── config.py          # Config loading (YAML)
│   └── endpoints/
│       ├── assets.py          # Character assets
│       ├── characters.py      # Character info, location, ship
│       ├── fitting_analysis.py # EFT parsing, stats, comparison, skill requirements
│       ├── fittings.py        # Ship fittings CRUD
│       ├── hauling.py         # Asset analysis & pickup-run planner
│       ├── market.py          # Orders, prices, blueprints, industry
│       ├── navigation.py      # Route planning & multi-stop optimization
│       ├── skills.py          # Skills, queue, attributes, implants
│       ├── universe.py        # Type info, system info, name resolution
│       └── wallet.py          # Wallet balance and journal
└── CLAUDE.md              # Agent instructions (Claude Code / Cursor)
```

---

## Scopes Reference

| Scope | Enables |
|---|---|
| `esi-skills.read_skills.v1` | `get_skills_summary`, `compare_skills_across_characters`, `check_fit_readiness` |
| `esi-skills.read_skillqueue.v1` | `get_skill_queue`, `get_character_attributes` |
| `esi-clones.read_implants.v1` | `get_active_implants` |
| `esi-assets.read_assets.v1` | `get_assets_list`, `search_assets`, `get_assets_summary`, `find_valuables_to_haul` |
| `esi-wallet.read_character_wallet.v1` | `get_wallet_balance`, `get_wallet_journal`, `compare_wallets` |
| `esi-fittings.read_fittings.v1` | `get_ship_fittings` |
| `esi-fittings.write_fittings.v1` | `save_ship_fitting` |
| `esi-markets.read_character_orders.v1` | `get_market_orders` |
| `esi-characters.read_blueprints.v1` | `get_blueprints_list` |
| `esi-industry.read_character_jobs.v1` | `get_industry_jobs_list` |
| `esi-location.read_location.v1` | `get_character_location`, `get_character_status`, `get_all_characters_status` |
| `esi-location.read_ship_type.v1` | `get_character_ship`, `get_character_status`, `get_all_characters_status` |
| `esi-contracts.read_character_contracts.v1` | Future: contract tools |
| `esi-universe.read_structures.v1` | Asset locations in player structures |

> **Note:** Fitting analysis tools (`get_ship_fit_stats`, `compare_ship_fits`, `get_fit_required_skills`) and universe/navigation tools (`plan_route`, `lookup_item_type`, etc.) use **public ESI endpoints** and don't require any scopes.

---

## Security Notes

- `tokens.json` and `config.yaml` are excluded from git via `.gitignore`
- Tokens are stored locally — never sent to any third party
- The MCP server only runs when your AI client is active
- All ESI calls go directly to `esi.evetech.net` over HTTPS
- The only write operation is `save_ship_fitting` — no ISK or items can be moved

---

## Troubleshooting

**`No authenticated characters` error**
```bash
python cli.py login   # run this first
```

**`400 Bad Request` during login**
- Make sure your `callback_url` in `config.yaml` exactly matches what you set in the EVE developer portal

**MCP tools not showing in Augment/Claude**
- Check that the `command` path points to the correct Python executable
- Make sure you've run `pip install -e .` in the project directory
- Reload VS Code / restart Claude Desktop after editing the config

**Scope errors on specific tools**
- Re-run `python cli.py login` after adding new scopes to `config.yaml`
- Make sure the new scopes are also added to your EVE developer application

---

*Built with [FastMCP](https://github.com/jlowin/fastmcp) · ESI data from [EVE Online ESI](https://esi.evetech.net/)*


