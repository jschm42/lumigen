from __future__ import annotations

from typing import Optional

import httpx

from app.config import Settings
from app.db import crud
from app.db.engine import SessionLocal
from app.services.model_config_service import ModelConfigService


class EnhancementService:
    def __init__(
        self, settings: Settings, model_config_service: ModelConfigService
    ) -> None:
        self._settings = settings
        self._secrets = model_config_service

    def _get_config(self) -> Optional[dict[str, str]]:
        with SessionLocal() as session:
            config = crud.get_enhancement_config(session)
            if not config:
                return None
            if not config.api_key_encrypted:
                return None
            api_key = self._secrets.decrypt_api_key(config.api_key_encrypted)
            return {
                "provider": config.provider,
                "model": config.model,
                "api_key": api_key,
            }

    async def enhance(self, prompt: str, enhancement_prompt: Optional[str]) -> str:
        config = self._get_config()
        if not config:
            raise ValueError("Enhancement LLM is not configured.")

        provider = config["provider"]
        model = config["model"]
        api_key = config["api_key"]

        messages = []
        if enhancement_prompt:
            messages.append({"role": "system", "content": enhancement_prompt})
        messages.append({"role": "user", "content": prompt})

        if provider == "openai":
            url = self._settings.openai_base_url.rstrip("/") + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
            }
        elif provider == "openrouter":
            url = self._settings.openrouter_base_url.rstrip("/") + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Title": self._settings.app_name,
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
            }
        else:
            raise ValueError("Enhancement provider is not supported yet.")

        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            raise ValueError(f"Enhancement request failed ({response.status_code}).")

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("Enhancement LLM returned no output.")

        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Enhancement LLM returned empty content.")

        return content.strip()
