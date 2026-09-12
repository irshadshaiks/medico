"""Complaint routing: correct pathway, or the safe generic fallback."""

from __future__ import annotations

import pytest

from app.services.questioning.complaint_classifier import classify_by_keywords, classify_complaint


@pytest.mark.parametrize(
    ("complaint", "expected"),
    [
        ("I have chest pain since morning", "chest_pain"),
        ("bukhar for three days", "fever"),
        ("pet dard, cannot eat", "abdominal_pain"),
        ("cough with phlegm for a month", "respiratory"),
        ("sir dard every morning", "headache"),
    ],
)
@pytest.mark.asyncio
async def test_known_complaints_route_correctly(complaint, expected):
    pathway, _ = await classify_complaint(complaint)
    assert pathway == expected


@pytest.mark.asyncio
async def test_unrecognised_complaint_falls_back_safely():
    pathway, decided_by = await classify_complaint("I feel generally unwell and tired")
    assert pathway == "generic"
    assert decided_by in {"keyword", "ai", "fallback"}


@pytest.mark.asyncio
async def test_empty_complaint_does_not_crash():
    pathway, decided_by = await classify_complaint("")
    assert pathway == "generic"
    assert decided_by == "empty"


def test_two_competing_complaints_defer_to_generic():
    # "chest pain and fever" is exactly the ambiguity the generic pathway exists for.
    assert classify_by_keywords("chest pain and fever together") is None
