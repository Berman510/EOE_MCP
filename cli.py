"""CLI entry point for EVE ESI Tool."""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console
from rich.table import Table

from eve_esi.config import AppConfig
from eve_esi.auth import EVEAuth
from eve_esi.client import ESIClient
from eve_esi.endpoints import characters, skills, assets, wallet, fittings, market, universe

console = Console()


def _load_config() -> AppConfig:
    try:
        return AppConfig.load()
    except ValueError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        sys.exit(1)


@click.group()
def main():
    """EVE Online ESI Tool - Manage your EVE characters and assets."""
    pass


@main.command()
def login():
    """Login with an EVE Online character via SSO."""
    config = _load_config()
    auth = EVEAuth(config)

    console.print("[bold blue]Opening EVE Online SSO login in your browser...[/bold blue]")
    console.print("Please authorize the application and wait for the callback.\n")

    try:
        token = auth.login()
        console.print(f"\n[green]✓ Successfully logged in as [bold]{token.character_name}[/bold] "
                      f"(ID: {token.character_id})[/green]")
        console.print(f"  Scopes: {len(token.scopes)} authorized")
    except Exception as e:
        console.print(f"\n[red]✗ Login failed: {e}[/red]")
        sys.exit(1)


@main.command("chars")
def list_characters():
    """List all authenticated characters."""
    config = _load_config()
    auth = EVEAuth(config)
    chars = auth.list_characters()

    if not chars:
        console.print("[yellow]No authenticated characters. Run 'login' first.[/yellow]")
        return

    table = Table(title="Authenticated Characters")
    table.add_column("Character ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Token Status", style="yellow")

    for cid, token in chars.items():
        status = "[green]Valid[/green]" if not token.is_expired else "[red]Expired[/red]"
        table.add_row(str(cid), token.character_name, status)

    console.print(table)


@main.command()
@click.argument("character_id", type=int, required=False)
def info(character_id: int | None):
    """Show character information."""
    config = _load_config()
    client = ESIClient(config, character_id)

    try:
        cid = character_id or client.character_id
        char_info = characters.get_character_info(client, cid)

        table = Table(title=f"Character: {char_info.get('name', 'Unknown')}")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Name", char_info.get("name", "Unknown"))
        table.add_row("Character ID", str(cid))
        table.add_row("Birthday", char_info.get("birthday", "Unknown"))
        table.add_row("Security Status", f"{char_info.get('security_status', 0):.2f}")

        if "corporation_id" in char_info:
            try:
                corp = characters.get_corporation_info(client, char_info["corporation_id"])
                table.add_row("Corporation", corp.get("name", str(char_info["corporation_id"])))
            except Exception:
                table.add_row("Corporation ID", str(char_info["corporation_id"]))

        if "alliance_id" in char_info:
            try:
                alliance = characters.get_alliance_info(client, char_info["alliance_id"])
                table.add_row("Alliance", alliance.get("name", str(char_info["alliance_id"])))
            except Exception:
                table.add_row("Alliance ID", str(char_info["alliance_id"]))

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@main.command("skills")
@click.argument("character_id", type=int, required=False)
def show_skills(character_id: int | None):
    """Show character skills summary."""
    config = _load_config()
    client = ESIClient(config, character_id)

    try:
        data = skills.get_skills(client)
        console.print(f"\n[bold]Total SP:[/bold] {data.get('total_sp', 0):,}")
        console.print(f"[bold]Unallocated SP:[/bold] {data.get('unallocated_sp', 0):,}")
        console.print(f"[bold]Skills Trained:[/bold] {len(data.get('skills', []))}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@main.command("queue")
@click.argument("character_id", type=int, required=False)
def show_queue(character_id: int | None):
    """Show current skill training queue."""
    config = _load_config()
    client = ESIClient(config, character_id)

    try:
        queue = skills.get_skill_queue(client)
        if not queue:
            console.print("[yellow]Skill queue is empty![/yellow]")
            return

        # Resolve skill names
        skill_ids = list({s["skill_id"] for s in queue})
        name_map = {}
        try:
            names = universe.resolve_names(client, skill_ids)
            name_map = {n["id"]: n["name"] for n in names}
        except Exception:
            pass

        table = Table(title="Skill Queue")
        table.add_column("#", style="cyan")
        table.add_column("Skill", style="green")
        table.add_column("Level", style="yellow")
        table.add_column("Finish Date", style="white")

        for entry in sorted(queue, key=lambda x: x.get("queue_position", 0)):
            skill_name = name_map.get(entry["skill_id"], str(entry["skill_id"]))
            table.add_row(
                str(entry.get("queue_position", "?")),
                skill_name,
                str(entry.get("finished_level", "?")),
                entry.get("finish_date", "Unknown"),
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@main.command("wallet")
@click.argument("character_id", type=int, required=False)
def show_wallet(character_id: int | None):
    """Show wallet balance."""
    config = _load_config()
    client = ESIClient(config, character_id)

    try:
        balance = wallet.get_wallet_balance(client)
        console.print(f"\n[bold green]Wallet Balance: {balance:,.2f} ISK[/bold green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()

