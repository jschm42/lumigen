from __future__ import annotations

import json
import logging
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
        self._settings = settings
        self._secrets = model_config_service

    def _get_config(self) -> dict[str, str] | None:
        with SessionLocal() as session:
            config = crud.get_enhancement_config(session)
            if not config:
                return None
            if config.api_key_encrypted:
                api_key = self._secrets.decrypt_api_key(config.api_key_encrypted)
            else:
                api_key = self._secrets.get_default_api_key(config.provider)
            
            if not api_key:
                return None
                
            return {
                "provider": config.provider,
                "model": config.model,
                "api_key": api_key,
                "default_prompt": config.default_enhancement_prompt,
            }

    async def enhance(
        self, 
        prompt: str, 
        model_specific_prompt: str | None = None,
        target_model: str = "Unknown",
        target_provider: str = "Unknown"
    ) -> dict[str, str]:
        """
        Enhance the given *prompt* using the configured LLM.
        Returns a dict with 'enhanced_prompt' and 'explanation'.
        """
        config = self._get_config()
        if not config:
            raise ValueError("Enhancement LLM is not configured")

        provider = config["provider"]
        model = config["model"]
        api_key = config["api_key"]
        global_default_prompt = config["default_prompt"]

        # Fallback logic for system prompt
        base_prompt = (
            model_specific_prompt or 
            global_default_prompt or 
            SAFE_DEFAULT_ENHANCEMENT_PROMPT
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
            target_provider=target_provider or "Unknown"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Enhance this prompt: {prompt}"}
        ]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
        }
        
        # Request JSON if supported (OpenAI / OpenRouter with specific models)
        # For now we just rely on the system prompt instructions.
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

        timeout = httpx.Timeout(60.0, connect=10.0)
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
            # Simple cleanup in case LLM wrapped it in markdown code blocks
            clean_content = content
            if clean_content.startswith("```json"):
                clean_content = clean_content[7:]
            if clean_content.endswith("```"):
                clean_content = clean_content[:-3]
            
            result = json.loads(clean_content.strip())
            
            # Validate keys
            if "enhanced_prompt" not in result:
                # Fallback if it's JSON but wrong keys
                return {
                    "enhanced_prompt": result.get("prompt", content),
                    "explanation": result.get("explanation", "Improved descriptive details.")
                }
            return result
        except json.JSONDecodeError:
            # Fallback for raw text output
            return {
                "enhanced_prompt": content,
                "explanation": "Improved descriptive details and artistic style."
            }
