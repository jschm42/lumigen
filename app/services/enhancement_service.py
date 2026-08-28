from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import Settings
from app.db import crud
from app.db.engine import SessionLocal
from app.services.model_config_service import ModelConfigService

logger = logging.getLogger(__name__)

SAFE_DEFAULT_ENHANCEMENT_PROMPT = """You are a prompt engineering expert for image generation models.
Your task is to take a simple user prompt and enhance it into a high-quality, detailed descriptive prompt.

GUIDELINES:
- Maintain the original intent and core subject of the user.
- Add descriptive details about lighting, textures, composition, and mood.
- Optimize the prompt specifically for the target model context provided below.
- Keep the response concise.
- IMPORTANT: You MUST return your response as a valid JSON object with the following keys:
  - "enhanced_prompt": The improved prompt text.
  - "explanation": A very brief (1 sentence) summary of what you improved.

CONTEXT:
Model: {target_model}
Provider: {target_provider}
"""

class EnhancementService:
    """Service that calls a configured LLM (OpenAI or OpenRouter) to enhance user prompts."""

    def __init__(
        self, settings: Settings, model_config_service: ModelConfigService
    ) -> None:
        """Initialize the enhancement service with application settings and secrets."""
        self._settings = settings
        self._secrets = model_config_service

    def _get_default_api_key(self, provider: str) -> str | None:
        getter = getattr(self._secrets, "get_default_api_key", None)
        if callable(getter):
            return getter(provider)
        return None

    def is_ready(self) -> bool:
        """Return True if any enhancement LLM configuration or supported provider API key is available."""
        if self._get_config() is not None:
            return True
        if self._get_default_api_key("openrouter"):
            return True
        if self._get_default_api_key("openai"):
            return True
        return False

    def list_available_llm_models(self) -> list[dict[str, str]]:
        """Return a list of available LLM model descriptors for the UI selectbox."""
        models: list[dict[str, str]] = []
        seen_ids: set[str] = set()

        config = self._get_config()
        if config and config.get("model"):
            model_id = f"{config['provider']}:{config['model']}"
            display_name = f"{config['model']} ({config['provider'].title()})"
            models.append({"id": model_id, "name": display_name, "provider": config["provider"]})
            seen_ids.add(model_id)

        has_openrouter = bool(self._get_default_api_key("openrouter"))
        has_openai = bool(self._get_default_api_key("openai"))

        curated_openrouter = [
            ("openrouter:openai/gpt-4o-mini", "OpenRouter: GPT-4o Mini"),
            ("openrouter:openai/gpt-4o", "OpenRouter: GPT-4o"),
            ("openrouter:anthropic/claude-3.5-sonnet", "OpenRouter: Claude 3.5 Sonnet"),
            ("openrouter:anthropic/claude-3.7-sonnet", "OpenRouter: Claude 3.7 Sonnet"),
            ("openrouter:google/gemini-2.0-flash-001", "OpenRouter: Gemini 2.0 Flash"),
            ("openrouter:meta-llama/llama-3.3-70b-instruct", "OpenRouter: Llama 3.3 70B"),
            ("openrouter:deepseek/deepseek-chat", "OpenRouter: DeepSeek V3"),
            ("openrouter:deepseek/deepseek-r1", "OpenRouter: DeepSeek R1"),
        ]

        curated_openai = [
            ("openai:gpt-4o-mini", "OpenAI: GPT-4o Mini"),
            ("openai:gpt-4o", "OpenAI: GPT-4o"),
            ("openai:o3-mini", "OpenAI: o3-mini"),
        ]

        if has_openrouter:
            for mid, mname in curated_openrouter:
                if mid not in seen_ids:
                    models.append({"id": mid, "name": mname, "provider": "openrouter"})
                    seen_ids.add(mid)

        if has_openai:
            for mid, mname in curated_openai:
                if mid not in seen_ids:
                    models.append({"id": mid, "name": mname, "provider": "openai"})
                    seen_ids.add(mid)

        return models

    def _get_config(self) -> dict[str, str] | None:
        """Fetch the database-stored enhancement config if present and populated with an API key."""
        with SessionLocal() as session:
            config = crud.get_enhancement_config(session)
            if not config:
                return None
            if config.api_key_encrypted:
                api_key = self._secrets.decrypt_api_key(config.api_key_encrypted)
            else:
                api_key = self._get_default_api_key(config.provider)

            if not api_key:
                return None

            return {
                "provider": config.provider,
                "model": config.model,
                "api_key": api_key,
                "default_prompt": config.default_enhancement_prompt,
            }

    def _resolve_llm(self, llm_model: str | None = None) -> tuple[str, str, str, str | None]:
        """
        Resolve (provider, model, api_key, default_prompt) for the requested LLM identifier or fallback.
        """
        default_config = self._get_config()

        if not llm_model or not llm_model.strip():
            if default_config:
                return (
                    default_config["provider"],
                    default_config["model"],
                    default_config["api_key"],
                    default_config.get("default_prompt"),
                )
            # Try auto-detecting openrouter or openai
            or_key = self._get_default_api_key("openrouter")
            if or_key:
                return "openrouter", "openai/gpt-4o-mini", or_key, None
            oa_key = self._get_default_api_key("openai")
            if oa_key:
                return "openai", "gpt-4o-mini", oa_key, None
            raise ValueError("Enhancement LLM is not configured")

        token = llm_model.strip()
        if ":" in token:
            provider, model = token.split(":", 1)
            provider = provider.lower().strip()
            model = model.strip()
        elif "/" in token:
            provider = "openrouter"
            model = token
        elif default_config:
            provider = default_config["provider"]
            model = token
        else:
            provider = "openai"
            model = token

        # Determine API key
        if default_config and default_config["provider"] == provider and (default_config["model"] == model or default_config.get("api_key")):
            api_key = default_config["api_key"]
            default_prompt = default_config.get("default_prompt")
        else:
            api_key = self._get_default_api_key(provider)
            default_prompt = default_config.get("default_prompt") if default_config else None

        if not api_key:
            raise ValueError(f"No API key configured for LLM provider '{provider}'")

        return provider, model, api_key, default_prompt

    async def enhance(
        self,
        prompt: str,
        model_specific_prompt: str | None = None,
        target_model: str = "Unknown",
        target_provider: str = "Unknown",
        llm_model: str | None = None,
    ) -> dict[str, str]:
        """
        Enhance the given *prompt* using the chosen or configured LLM.
        Returns a dict with 'enhanced_prompt' and 'explanation'.
        """
        provider, model, api_key, global_default_prompt = self._resolve_llm(llm_model)

        # Fallback logic for system prompt
        base_prompt = (
            model_specific_prompt
            or global_default_prompt
            or SAFE_DEFAULT_ENHANCEMENT_PROMPT
        )

        # Always append JSON requirements to ensure the UI can parse the response,
        # unless the user has already explicitly included JSON instructions.
        json_instr = (
            "IMPORTANT: You MUST return your response as a valid JSON object with the following keys:\n"
            '  - "enhanced_prompt": The improved prompt text.\n'
            '  - "explanation": A very brief (1 sentence) summary of what you improved.'
        )

        if "enhanced_prompt" not in base_prompt:
            system_prompt_template = base_prompt + "\n\n" + json_instr
        else:
            system_prompt_template = base_prompt

        # Inject context if placeholders exist
        system_prompt = system_prompt_template.format(
            target_model=target_model or "Unknown",
            target_provider=target_provider or "Unknown",
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Enhance this prompt: {prompt}"},
        ]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
        }

        if provider == "openai":
            url = self._settings.openai_base_url.rstrip("/") + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            if "gpt-4o" in model or "gpt-3.5-turbo-0125" in model:
                payload["response_format"] = {"type": "json_object"}
        elif provider == "openrouter":
            url = self._settings.openrouter_base_url.rstrip("/") + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Title": self._settings.app_name,
            }
        else:
            raise ValueError(f"Enhancement provider '{provider}' is not supported yet")

        timeout = httpx.Timeout(
            self._settings.llm_enhancement_timeout_seconds,
            connect=self._settings.llm_enhancement_connect_timeout_seconds,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"Enhancement LLM error: {e.response.text}")
                raise ValueError(f"Enhancement request failed: {e.response.status_code}") from e
            except Exception as e:
                logger.error(f"Enhancement request exception: {e}")
                raise ValueError(f"Failed to connect to enhancement LLM: {e}") from e

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("Enhancement LLM returned no output")

        content = choices[0].get("message", {}).get("content", "").strip()
        if not content:
            raise ValueError("Enhancement LLM returned empty content")

        # Try to parse as JSON
        try:
            clean_content = content
            if clean_content.startswith("```json"):
                clean_content = clean_content[7:]
            if clean_content.endswith("```"):
                clean_content = clean_content[:-3]

            result = json.loads(clean_content.strip())

            # Validate keys
            if "enhanced_prompt" not in result:
                return {
                    "enhanced_prompt": result.get("prompt", content),
                    "explanation": result.get("explanation", "Improved descriptive details."),
                }
            return result
        except json.JSONDecodeError:
            return {
                "enhanced_prompt": content,
                "explanation": "Improved descriptive details and artistic style.",
            }
