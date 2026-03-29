"""Configuration management for EVE ESI Tool."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


DEFAULT_SCOPES = [
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-characters.read_blueprints.v1",
    "esi-assets.read_assets.v1",
    "esi-wallet.read_character_wallet.v1",
    "esi-fittings.read_fittings.v1",
    "esi-fittings.write_fittings.v1",
    "esi-markets.read_character_orders.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-location.read_location.v1",
    "esi-location.read_ship_type.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-universe.read_structures.v1",
]

ESI_BASE_URL = "https://esi.evetech.net/latest"
ESI_AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize"
ESI_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
ESI_JWKS_URL = "https://login.eveonline.com/oauth/jwks"
ESI_VERIFY_URL = "https://login.eveonline.com/oauth/verify"


class SSOConfig(BaseModel):
    """EVE SSO configuration."""
    client_id: str
    client_secret: Optional[str] = None
    callback_url: str = "http://localhost:8182/callback"
    scopes: list[str] = Field(default_factory=lambda: DEFAULT_SCOPES.copy())


class TokenStorageConfig(BaseModel):
    """Token storage configuration."""
    path: str = "tokens.json"


class AppConfig(BaseModel):
    """Full application configuration."""
    eve_sso: SSOConfig
    token_storage: TokenStorageConfig = Field(default_factory=TokenStorageConfig)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "AppConfig":
        """Load config from YAML file or environment variables."""
        if config_path is None:
            # Look for config.yaml in current dir, then in project root
            for candidate in ["config.yaml", Path(__file__).parent.parent / "config.yaml"]:
                if Path(candidate).exists():
                    config_path = str(candidate)
                    break

        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                data = yaml.safe_load(f)
            return cls(**data)

        # Fall back to environment variables
        client_id = os.environ.get("EVE_CLIENT_ID")
        client_secret = os.environ.get("EVE_CLIENT_SECRET")
        callback_url = os.environ.get("EVE_CALLBACK_URL", "http://localhost:8182/callback")

        if not client_id:
            raise ValueError(
                "No config.yaml found and EVE_CLIENT_ID environment variable not set.\n"
                "Copy config.example.yaml to config.yaml and fill in your EVE application credentials,\n"
                "or set EVE_CLIENT_ID (and optionally EVE_CLIENT_SECRET) environment variables.\n"
                "Register an application at https://developers.eveonline.com/"
            )

        return cls(
            eve_sso=SSOConfig(
                client_id=client_id,
                client_secret=client_secret,
                callback_url=callback_url,
            )
        )

