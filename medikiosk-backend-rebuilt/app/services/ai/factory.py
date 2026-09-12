"""Resolves the configured AI provider once per process."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.base import AIService
from app.services.ai.mock_adapter import MockAIService

log = get_logger(__name__)


@lru_cache
def get_ai_service() -> AIService:
    if settings.AI_PROVIDER == "gemini":
        try:
            from app.services.ai.gemini_adapter import GeminiAIService

            return GeminiAIService()
        except Exception as exc:  # noqa: BLE001
            # A missing key or SDK must not stop the server from booting; the
            # mock keeps every route working and the log says exactly why.
            log.error("Gemini unavailable, falling back to mock", extra={"extra": {"error": str(exc)[:200]}})
            return MockAIService()
    return MockAIService()
