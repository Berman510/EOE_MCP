"""ESI API client with automatic token refresh and pagination support."""

from __future__ import annotations

import time
from typing import Any, Optional

import requests

from eve_esi.auth import EVEAuth, TokenData
from eve_esi.config import AppConfig, ESI_BASE_URL


class ESIError(Exception):
    """ESI API error."""
    def __init__(self, status_code: int, message: str, error_data: dict | None = None):
        self.status_code = status_code
        self.error_data = error_data or {}
        super().__init__(f"ESI Error {status_code}: {message}")


class ESIClient:
    """EVE ESI API client with automatic token refresh."""

    def __init__(self, config: AppConfig, character_id: Optional[int] = None):
        self.config = config
        self.auth = EVEAuth(config)
        self._character_id = character_id
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "EVE-ESI-Tool/0.1.0",
        })

    @property
    def character_id(self) -> int:
        if self._character_id is None:
            chars = self.auth.list_characters()
            if not chars:
                raise RuntimeError("No authenticated characters. Run login first.")
            # Use the first character by default
            self._character_id = next(iter(chars))
        return self._character_id

    @character_id.setter
    def character_id(self, value: int) -> None:
        self._character_id = value

    def _get_token(self) -> TokenData:
        """Get a valid token for the current character."""
        token = self.auth.get_valid_token(self.character_id)
        if token is None:
            raise RuntimeError(
                f"No token found for character {self.character_id}. Run login first."
            )
        return token

    def _request(
        self,
        method: str,
        path: str,
        authenticated: bool = True,
        params: dict | None = None,
        json_data: Any = None,
    ) -> requests.Response:
        """Make an ESI API request with automatic auth and error handling."""
        url = f"{ESI_BASE_URL}{path}"
        headers = {}

        if authenticated:
            token = self._get_token()
            headers["Authorization"] = f"Bearer {token.access_token}"

        resp = self._session.request(
            method, url, params=params, json=json_data, headers=headers
        )

        if resp.status_code == 420:
            # Error limited - wait and retry
            retry_after = int(resp.headers.get("Retry-After", "60"))
            time.sleep(retry_after)
            return self._request(method, path, authenticated, params, json_data)

        if resp.status_code >= 400:
            try:
                error_data = resp.json()
                message = error_data.get("error", resp.reason)
            except Exception:
                error_data = None
                message = resp.reason
            raise ESIError(resp.status_code, message, error_data)

        return resp

    def get(self, path: str, authenticated: bool = True, params: dict | None = None) -> Any:
        """GET request, returns JSON response."""
        resp = self._request("GET", path, authenticated, params)
        if resp.status_code == 204:
            return None
        return resp.json()

    def get_paginated(self, path: str, authenticated: bool = True, params: dict | None = None) -> list:
        """GET paginated endpoint, returns all pages combined."""
        params = dict(params or {})
        params["page"] = 1
        all_items = []

        while True:
            resp = self._request("GET", path, authenticated, params)
            items = resp.json()
            if not items:
                break
            all_items.extend(items)
            total_pages = int(resp.headers.get("X-Pages", "1"))
            if params["page"] >= total_pages:
                break
            params["page"] += 1

        return all_items

    def post(self, path: str, json_data: Any = None, authenticated: bool = True) -> Any:
        """POST request, returns JSON response."""
        resp = self._request("POST", path, authenticated, json_data=json_data)
        if resp.status_code == 204:
            return None
        return resp.json()

    def delete(self, path: str, authenticated: bool = True) -> None:
        """DELETE request."""
        self._request("DELETE", path, authenticated)

