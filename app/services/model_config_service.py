from __future__ import annotations

from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings
from app.db import crud
from app.db.engine import SessionLocal


class ModelConfigService:
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

    def get_api_key(self, model_config_id: int) -> Optional[str]:
        with SessionLocal() as session:
            config = crud.get_model_config(session, model_config_id)
            if not config or not config.api_key_encrypted:
                return None
            return self.decrypt_api_key(config.api_key_encrypted)
