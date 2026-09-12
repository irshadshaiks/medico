"""
Translation seam.

UI strings are static i18n JSON on the client and never come through here.
This is only for dynamic content — a document read in Kannada that a doctor
needs in English.
"""

from __future__ import annotations

import abc

from app.services.ai.base import AICompletionRequest
from app.services.ai.factory import get_ai_service


class TranslationService(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    async def translate(self, text: str, target_language: str) -> str: ...


class AITranslationService(TranslationService):
    """Reuses the configured LLM rather than adding a second vendor."""

    name = "ai"

    async def translate(self, text: str, target_language: str) -> str:
        if not text.strip():
            return text
        ai = get_ai_service()
        response = await ai.complete(
            AICompletionRequest(
                prompt=(
                    f"Translate the text below into {target_language}. Translate only; "
                    f"do not summarise, explain, or add anything.\n\n---\n{text[:4000]}\n---"
                ),
                temperature=0.0,
            ),
            fallback=text,  # untranslated beats blank
        )
        return response.text


def get_translation_service() -> TranslationService:
    return AITranslationService()
