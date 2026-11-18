from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings
from app.db import crud
from app.db.engine import SessionLocal
from app.providers.base import EndpointConfig, ProviderConfigError


class ModelConfigService:
    """Service for encrypting/decrypting provider API keys and resolving the active key for a provider."""

    # Mapping of provider names to settings attribute names
    PROVIDER_API_KEY_ATTR = {
        "openai": "openai_api_key",
        "openrouter": "openrouter_api_key",
        "google": "google_api_key",
        "bfl": "bfl_api_key",
        "fal": "fal_api_key",
        "minimax": "minimax_api_key",
        "stability": "stability_api_key",
        "replicate": "replicate_api_key",
        "together": "together_api_key",
        "xai": "xai_api_key",
        "ideogram": "ideogram_api_key",
        "byteplus": "byteplus_api_key",
        "seedance": "seedance_api_key",
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _fernet(self) -> Fernet:
        key = (self._settings.provider_config_key or "").strip()
        if not key:
            raise ValueError("PROVIDER_CONFIG_KEY is not set.")
        return Fernet(key.encode("ascii"))

    def encrypt_api_key(self, value: str) -> str:
        """Encrypt *value* with Fernet and return the ASCII token string."""
        token = self._fernet().encrypt(value.encode("utf-8"))
        return token.decode("ascii")

    def decrypt_api_key(self, token: str) -> str:
        """Decrypt a Fernet *token* and return the plaintext API key string."""
        try:
            raw = self._fernet().decrypt(token.encode("ascii"))
        except InvalidToken as exc:
            raise ValueError(
                "Invalid encrypted API key or PROVIDER_CONFIG_KEY."
            ) from exc
        return raw.decode("utf-8")

    def get_api_key(self, model_config_id: int) -> str | None:
        """Get the custom API key for a model config if use_custom_api_key is True."""
        with SessionLocal() as session:
            config = crud.get_model_config(session, model_config_id)
            if not config or not config.use_custom_api_key or not config.api_key_encrypted:
                return None
            return self.decrypt_api_key(config.api_key_encrypted)

    def get_provider_api_key(self, provider: str) -> str | None:
        """Get the centrally stored provider API key from the DB, if configured."""
        with SessionLocal() as session:
            row = crud.get_provider_api_key(session, provider.lower())
            if not row or not row.api_key_encrypted:
                return None
            try:
                return self.decrypt_api_key(row.api_key_encrypted)
            except (ValueError, Exception):
                return None

    def get_default_api_key(self, provider: str) -> str | None:
        """Get the API key for a provider: DB-stored key takes priority over .env."""
        provider_lower = provider.lower()
        db_key = self.get_provider_api_key(provider_lower)
        if db_key:
            return db_key
        attr_name = self.PROVIDER_API_KEY_ATTR.get(provider_lower)
        if not attr_name:
            return None
        env_key = getattr(self._settings, attr_name, None)
        if not env_key and provider_lower == "seedance":
            # Seedance runs on BytePlus ModelArk, so the BytePlus key works too.
            env_key = getattr(self._settings, "byteplus_api_key", None)
        return env_key

    def has_env_api_key(self, provider: str) -> bool:
        """Return True if the provider has an API key set in the environment (.env)."""
        attr_name = self.PROVIDER_API_KEY_ATTR.get(provider.lower())
        if not attr_name:
            return False
        return bool(getattr(self._settings, attr_name, None))

    def get_model_config(self, model_config_id: int):
        """Get a model config by ID."""
        with SessionLocal() as session:
            return crud.get_model_config(session, model_config_id)

    def endpoint_config_for(self, model_config) -> EndpointConfig | None:
        """Return the custom endpoint connection for *model_config*, or None for built-in providers.

        Raises ``ProviderConfigError`` when the linked endpoint is missing or deactivated.
        """
        endpoint_id = getattr(model_config, "endpoint_id", None)
        if not endpoint_id:
            return None
        with SessionLocal() as session:
            endpoint = crud.get_custom_endpoint(session, int(endpoint_id))
            if endpoint is None:
                raise ProviderConfigError(f"The endpoint of model {model_config.name!r} no longer exists.")
            if not endpoint.is_active:
                raise ProviderConfigError(f"Endpoint {endpoint.name!r} is deactivated (Admin -> Endpoints).")
            return self.endpoint_config_from_row(endpoint, getattr(model_config, "provider_options", None))

    def endpoint_config_from_row(self, endpoint, options: dict | None = None) -> EndpointConfig:
        """Build an ``EndpointConfig`` from a ``CustomEndpoint`` row, decrypting its optional API key."""
        api_key = self.decrypt_api_key(endpoint.api_key_encrypted) if endpoint.api_key_encrypted else None
        return EndpointConfig(
            id=endpoint.id,
            name=endpoint.name,
            kind=endpoint.kind,
            base_url=endpoint.base_url,
            api_key=api_key,
            options=dict(options or {}),
        )

    def get_reasoning_model_api_key(self, reasoning_model_id: int) -> str | None:
        """Get custom API key for a reasoning model config if enabled, else provider key."""
        with SessionLocal() as session:
            config = crud.get_reasoning_model_config(session, reasoning_model_id)
            if not config:
                return None
            if config.use_custom_api_key and config.api_key_encrypted:
                return self.decrypt_api_key(config.api_key_encrypted)
            return self.get_default_api_key(config.provider)
