"""
The AI seam.

Everything downstream — questioning, classification, extraction, summaries —
calls `AIService.complete()` or `.complete_json()`. Neither of those is
overridable by an adapter: `BaseAIService` owns the safety preamble, the
timeout, the retries and the fallback, and adapters only implement the raw
`_call()` to their vendor. That way a new provider cannot accidentally ship
without the Section 11 constraints attached.
"""

from __future__ import annotations

import abc
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.core.prompts import SAFETY_PREAMBLE

log = get_logger(__name__)


@dataclass(slots=True)
class AICompletionRequest:
    prompt: str
    temperature: float = 0.2
    max_output_tokens: int = 900
    # Extra instruction appended after the safety preamble, never replacing it.
    system_suffix: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AICompletionResponse:
    text: str
    provider: str
    model: str | None = None
    # True when every attempt failed and this is the safe canned answer.
    degraded: bool = False
    latency_ms: int | None = None


class AIService(abc.ABC):
    """The interface the rest of the application is allowed to know about."""

    name: str = "abstract"

    @abc.abstractmethod
    async def _call(self, system: str, prompt: str, req: AICompletionRequest) -> str: ...

    @abc.abstractmethod
    async def health(self) -> bool: ...


class BaseAIService(AIService):
    """Shared call path: preamble, timeout, retry with backoff, graceful fallback."""

    async def complete(
        self, request: AICompletionRequest, *, fallback: str | None = None
    ) -> AICompletionResponse:
        system = SAFETY_PREAMBLE
        if request.system_suffix:
            system = f"{system}\n\n{request.system_suffix}"

        last_error: Exception | None = None
        for attempt in range(settings.AI_MAX_RETRIES + 1):
            started = asyncio.get_event_loop().time()
            try:
                text = await asyncio.wait_for(
                    self._call(system, request.prompt, request),
                    timeout=settings.AI_TIMEOUT_SECONDS,
                )
                latency = int((asyncio.get_event_loop().time() - started) * 1000)
                return AICompletionResponse(
                    text=text.strip(), provider=self.name, model=settings.GEMINI_MODEL, latency_ms=latency
                )
            except (TimeoutError, asyncio.TimeoutError) as exc:
                last_error = exc
                log.warning("AI call timed out", extra={"extra": {"attempt": attempt, "provider": self.name}})
            except Exception as exc:  # noqa: BLE001 - any vendor error is retryable here
                last_error = exc
                log.warning(
                    "AI call failed",
                    extra={"extra": {"attempt": attempt, "provider": self.name, "error": str(exc)[:200]}},
                )
            if attempt < settings.AI_MAX_RETRIES:
                await asyncio.sleep(0.4 * (2**attempt))

        # Graceful degradation. A dead LLM must never take the intake down with
        # it — the caller supplies a safe templated string to use instead.
        if fallback is not None:
            log.error("AI unavailable, using fallback", extra={"extra": {"provider": self.name}})
            return AICompletionResponse(text=fallback, provider=self.name, degraded=True)
        raise ProviderUnavailable(f"AI provider '{self.name}' is unavailable.") from last_error

    async def complete_json(
        self, request: AICompletionRequest, *, fallback: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], bool]:
        """
        Ask for JSON and parse it defensively. Models wrap JSON in fences,
        prefix it with prose, or trail a sentence after it; all three are
        recovered here rather than crashing an intake.
        """
        response = await self.complete(request, fallback=None if fallback is None else "")
        if response.degraded:
            return (fallback or {}), True

        parsed = _extract_json(response.text)
        if parsed is None:
            log.warning("AI returned unparseable JSON", extra={"extra": {"preview": response.text[:200]}})
            return (fallback or {}), True
        return parsed, False


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    # Last resort: the outermost balanced object in the string.
    start, depth = text.find("{"), 0
    if start == -1:
        return None
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[start : i + 1])
                    return value if isinstance(value, dict) else None
                except json.JSONDecodeError:
                    return None
    return None
