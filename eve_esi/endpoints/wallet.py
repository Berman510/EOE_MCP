"""Wallet and financial endpoints."""

from __future__ import annotations

from typing import Any

from eve_esi.client import ESIClient


def get_wallet_balance(client: ESIClient) -> float:
    """Get the wallet balance (ISK) of the authenticated character."""
    return client.get(f"/characters/{client.character_id}/wallet/")


def get_wallet_journal(client: ESIClient) -> list[dict[str, Any]]:
    """Get the wallet journal (transaction history) of the authenticated character.

    Returns list of journal entries with:
        - id, date, ref_type, amount, balance
        - first_party_id, second_party_id, description, reason
    """
    return client.get_paginated(f"/characters/{client.character_id}/wallet/journal/")


def get_wallet_transactions(client: ESIClient) -> list[dict[str, Any]]:
    """Get wallet transactions of the authenticated character.

    Returns list of transactions with:
        - transaction_id, date, type_id, quantity, unit_price
        - client_id, location_id, is_buy, is_personal
    """
    return client.get(f"/characters/{client.character_id}/wallet/transactions/")

