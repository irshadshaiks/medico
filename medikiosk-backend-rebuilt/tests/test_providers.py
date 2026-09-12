"""
Provider-seam tests (Module 12's acceptance criteria).

The point of the abstraction is that configuration decides the adapter and a
dead provider degrades instead of crashing. Both are asserted here.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.ai.base import AICompletionRequest, BaseAIService, _extract_json
from app.services.ai.factory import get_ai_service
from app.services.ai.mock_adapter import MockAIService


class AlwaysFailing(BaseAIService):
    name = "always-failing"

    def __init__(self):
        self.calls = 0

    async def _call(self, system, prompt, req):
        self.calls += 1
        raise RuntimeError("simulated provider outage")

    async def health(self):
        return False


class SlowProvider(BaseAIService):
    name = "slow"

    async def _call(self, system, prompt, req):
        await asyncio.sleep(60)
        return "never returned"

    async def health(self):
        return False


def test_factory_resolves_mock_by_default():
    assert get_ai_service().name == "mock"


@pytest.mark.asyncio
async def test_failure_retries_then_falls_back():
    provider = AlwaysFailing()
    response = await provider.complete(
        AICompletionRequest(prompt="anything"), fallback="templated question"
    )
    assert response.degraded is True
    assert response.text == "templated question"
    assert provider.calls > 1, "the wrapper should have retried before giving up"


@pytest.mark.asyncio
async def test_no_fallback_raises_rather_than_returning_nonsense():
    from app.core.errors import ProviderUnavailable

    with pytest.raises(ProviderUnavailable):
        await AlwaysFailing().complete(AICompletionRequest(prompt="anything"))


@pytest.mark.asyncio
async def test_safety_preamble_is_attached_to_every_call():
    seen: dict = {}

    class Capturing(BaseAIService):
        name = "capturing"

        async def _call(self, system, prompt, req):
            seen["system"] = system
            return "ok"

        async def health(self):
            return True

    await Capturing().complete(AICompletionRequest(prompt="hello"))
    assert "never diagnose" in seen["system"].lower()
    assert "never invent information" in seen["system"].lower()


@pytest.mark.asyncio
async def test_mock_classifier_routes_chest_pain_and_fever():
    provider = MockAIService()
    chest = await provider.complete(
        AICompletionRequest(prompt="choose which intake pathway\nPatient's description: I have chest pain")
    )
    fever = await provider.complete(
        AICompletionRequest(prompt="choose which intake pathway\nPatient's description: I have fever")
    )
    assert chest.text == "chest_pain"
    assert fever.text == "fever"


@pytest.mark.parametrize(
    "raw",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Here is the JSON you asked for:\n{"a": 1}\nHope that helps.',
    ],
)
def test_json_extraction_survives_model_formatting(raw):
    assert _extract_json(raw) == {"a": 1}


def test_json_extraction_returns_none_on_garbage():
    assert _extract_json("I could not read that document.") is None
