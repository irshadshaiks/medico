"""Gemini adapter. The key is read from config and never logged or returned."""

from __future__ import annotations

import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.base import AICompletionRequest, BaseAIService

log = get_logger(__name__)


class GeminiAIService(BaseAIService):
    name = "gemini"

    def __init__(self) -> None:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER=gemini.")
        import google.generativeai as genai  # imported lazily so the mock path needs no SDK

        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._genai = genai

    async def _call(self, system: str, prompt: str, req: AICompletionRequest) -> str:
        model = self._genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=system,
            generation_config={
                "temperature": req.temperature,
                "max_output_tokens": req.max_output_tokens,
            },
        )
        # The SDK's async surface is thin; a thread keeps the event loop free.
        result = await asyncio.to_thread(model.generate_content, prompt)
        text = getattr(result, "text", None)
        if not text:
            # Usually a safety block. Treated as a provider failure so the
            # retry/fallback path handles it rather than returning empty prose.
            raise RuntimeError("Gemini returned no text (possibly a safety block).")
        return text

    async def health(self) -> bool:
        try:
            await self._call(
                "Reply with the single word: ok",
                "ping",
                AICompletionRequest(prompt="ping", max_output_tokens=8),
            )
            return True
        except Exception:  # noqa: BLE001
            return False
