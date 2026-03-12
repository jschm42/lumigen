from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings
from app.db import crud
from app.db.engine import SessionLocal


class ModelConfigService:
    # Mapping of provider names to settings attribute names
    PROVIDER_API_KEY_ATTR = {
        "openai": "openai_api_key",
        "openrouter": "openrouter_api_key",
        "google": "google_api_key",
        "bfl": "bfl_api_key",
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _fernet(self) -> Fernet:
        key = (self._settings.provider_config_key or "").strip()
        if not key:
            raise ValueError("PROVIDER_CONFIG_KEY is not set.")
        return Fernet(key.encode("ascii"))

    def encrypt_api_key(self, value: str) -> str:
        token = self._fernet().encrypt(value.encode("utf-8"))
        return token.decode("ascii")

    def decrypt_api_key(self, token: str) -> str:
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
            if not row:
                return None
            return self.decrypt_api_key(row.api_key_encrypted)

    def get_default_api_key(self, provider: str) -> str | None:
        """Get the API key for a provider: DB-stored key takes priority over .env."""
        db_key = self.get_provider_api_key(provider)
        if db_key:
            return db_key
        attr_name = self.PROVIDER_API_KEY_ATTR.get(provider.lower())
        if not attr_name:
            return None
        return getattr(self._settings, attr_name, None)

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
