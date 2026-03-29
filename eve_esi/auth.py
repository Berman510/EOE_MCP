"""EVE Online SSO OAuth2 authentication with PKCE support."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from pydantic import BaseModel

from eve_esi.config import AppConfig, ESI_AUTH_URL, ESI_TOKEN_URL


class TokenData(BaseModel):
    """Stored token data for a character."""
    character_id: int
    character_name: str
    access_token: str
    refresh_token: str
    expires_at: float
    scopes: list[str]

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60  # 60s buffer


class TokenStore:
    """Manages persistent storage of OAuth tokens."""

    def __init__(self, path: str = "tokens.json"):
        self.path = Path(path)
        self._tokens: dict[int, TokenData] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    data = json.load(f)
                for char_id_str, token_data in data.items():
                    self._tokens[int(char_id_str)] = TokenData(**token_data)
            except (json.JSONDecodeError, Exception):
                self._tokens = {}

    def _save(self) -> None:
        data = {str(k): v.model_dump() for k, v in self._tokens.items()}
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def get(self, character_id: int) -> Optional[TokenData]:
        return self._tokens.get(character_id)

    def get_all(self) -> dict[int, TokenData]:
        return dict(self._tokens)

    def save_token(self, token: TokenData) -> None:
        self._tokens[token.character_id] = token
        self._save()

    def remove(self, character_id: int) -> None:
        self._tokens.pop(character_id, None)
        self._save()


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth2 callback."""
    auth_code: Optional[str] = None
    auth_state: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            _CallbackHandler.auth_state = params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Login successful!</h1>"
                b"<p>You can close this window and return to the application.</p>"
                b"</body></html>"
            )
        elif "error" in params:
            _CallbackHandler.error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            msg = params.get("error_description", [params["error"][0]])[0]
            self.wfile.write(f"<html><body><h1>Login failed</h1><p>{msg}</p></body></html>".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args) -> None:
        pass  # Suppress HTTP server logs


class EVEAuth:
    """Handles EVE Online SSO OAuth2 authentication flow."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.token_store = TokenStore(config.token_storage.path)

    def get_valid_token(self, character_id: int) -> Optional[TokenData]:
        """Get a valid (non-expired) token for a character, refreshing if needed."""
        token = self.token_store.get(character_id)
        if token is None:
            return None
        if token.is_expired:
            token = self._refresh_token(token)
        return token

    def list_characters(self) -> dict[int, TokenData]:
        """List all stored character tokens."""
        return self.token_store.get_all()

    @property
    def _use_pkce(self) -> bool:
        """Use PKCE flow when no client secret is configured."""
        return not self.config.eve_sso.client_secret

    def login(self) -> TokenData:
        """Run the full OAuth2 login flow. Opens browser and waits for callback."""
        state = secrets.token_urlsafe(32)
        code_verifier = None

        # Build authorization URL
        params = {
            "response_type": "code",
            "redirect_uri": self.config.eve_sso.callback_url,
            "client_id": self.config.eve_sso.client_id,
            "scope": " ".join(self.config.eve_sso.scopes),
            "state": state,
        }

        if self._use_pkce:
            # PKCE flow: generate code challenge (no client secret)
            code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
            code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).rstrip(b"=").decode()
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        auth_url = f"{ESI_AUTH_URL}?{urlencode(params)}"

        # Parse callback URL to get port
        parsed_callback = urlparse(self.config.eve_sso.callback_url)
        port = parsed_callback.port or 8182

        # Reset handler state
        _CallbackHandler.auth_code = None
        _CallbackHandler.auth_state = None
        _CallbackHandler.error = None

        # Start local server for callback
        server = HTTPServer(("localhost", port), _CallbackHandler)
        server.timeout = 120  # 2 minute timeout

        # Open browser
        webbrowser.open(auth_url)

        # Wait for callback
        while _CallbackHandler.auth_code is None and _CallbackHandler.error is None:
            server.handle_request()

        server.server_close()

        if _CallbackHandler.error:
            raise RuntimeError(f"SSO login failed: {_CallbackHandler.error}")

        if _CallbackHandler.auth_state != state:
            raise RuntimeError("State mismatch - possible CSRF attack")

        # Exchange code for tokens
        return self._exchange_code(_CallbackHandler.auth_code, code_verifier)

    def _exchange_code(self, code: str, code_verifier: str | None) -> TokenData:
        """Exchange authorization code for access and refresh tokens."""
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        if self._use_pkce:
            # PKCE flow: send code_verifier and client_id in body, no Basic Auth
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.config.eve_sso.client_id,
                "code_verifier": code_verifier,
            }
            resp = requests.post(ESI_TOKEN_URL, data=data, headers=headers)
        else:
            # Standard flow: Basic Auth with client_id:client_secret
            data = {
                "grant_type": "authorization_code",
                "code": code,
            }
            basic_auth = base64.urlsafe_b64encode(
                f"{self.config.eve_sso.client_id}:{self.config.eve_sso.client_secret}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {basic_auth}"
            resp = requests.post(ESI_TOKEN_URL, data=data, headers=headers)

        resp.raise_for_status()
        token_resp = resp.json()

        # Verify the token and get character info
        char_info = self._verify_token(token_resp["access_token"])

        token = TokenData(
            character_id=char_info["character_id"],
            character_name=char_info["character_name"],
            access_token=token_resp["access_token"],
            refresh_token=token_resp["refresh_token"],
            expires_at=time.time() + token_resp["expires_in"],
            scopes=char_info.get("scopes", []),
        )
        self.token_store.save_token(token)
        return token

    def _refresh_token(self, token: TokenData) -> TokenData:
        """Refresh an expired access token."""
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        if self._use_pkce:
            # PKCE flow: send client_id in body, no Basic Auth
            data = {
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
                "client_id": self.config.eve_sso.client_id,
            }
            resp = requests.post(ESI_TOKEN_URL, data=data, headers=headers)
        else:
            # Standard flow: Basic Auth with client_id:client_secret
            data = {
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
            }
            basic_auth = base64.urlsafe_b64encode(
                f"{self.config.eve_sso.client_id}:{self.config.eve_sso.client_secret}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {basic_auth}"
            resp = requests.post(ESI_TOKEN_URL, data=data, headers=headers)
        resp.raise_for_status()
        token_resp = resp.json()

        char_info = self._verify_token(token_resp["access_token"])

        new_token = TokenData(
            character_id=char_info["character_id"],
            character_name=char_info["character_name"],
            access_token=token_resp["access_token"],
            refresh_token=token_resp.get("refresh_token", token.refresh_token),
            expires_at=time.time() + token_resp["expires_in"],
            scopes=char_info.get("scopes", token.scopes),
        )
        self.token_store.save_token(new_token)
        return new_token

    def _verify_token(self, access_token: str) -> dict:
        """Decode JWT token to get character information."""
        # The access token is a JWT - decode the payload without verification
        # (we trust the token since we just got it from CCP's servers)
        parts = access_token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT token format")

        # Decode payload (add padding if needed)
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))

        # Extract character info from JWT subject
        # Format: "CHARACTER:EVE:123456789"
        sub = decoded.get("sub", "")
        parts = sub.split(":")
        if len(parts) != 3 or parts[0] != "CHARACTER" or parts[1] != "EVE":
            raise ValueError(f"Unexpected JWT subject format: {sub}")

        # Extract scopes from JWT scp claim
        scp = decoded.get("scp", [])
        if isinstance(scp, str):
            scp = [scp]

        return {
            "character_id": int(parts[2]),
            "character_name": decoded.get("name", "Unknown"),
            "scopes": scp,
        }

    def logout(self, character_id: int) -> None:
        """Remove stored tokens for a character."""
        self.token_store.remove(character_id)

