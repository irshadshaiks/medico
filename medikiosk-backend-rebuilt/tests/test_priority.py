"""
Priority scoring tests.

The queue is where this system either helps or hurts. These assert the two
things that would make it hurt: an elderly, severely limited patient being
buried under a young one with a soft flag, and a long-waiting patient being
starved indefinitely.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.enums import PriorityLevel, Severity
from app.services.triage.priority_engine import BAND_PRIORITY, assess


@dataclass
class FakeFlag:
    severity: Severity
    label: str = "reported symptom"


PRIORITY_FLAG = FakeFlag(Severity.PRIORITY, "Chest discomfort on exertion")
REVIEW_FLAG = FakeFlag(Severity.REVIEW, "Fainting reported")


def test_priority_flag_alone_reaches_the_top_band():
    result = assess(facts={}, flags=[PRIORITY_FLAG], age=40, waited_minutes=0)
    assert result.level is PriorityLevel.PRIORITY
    assert result.score >= BAND_PRIORITY


def test_soft_factors_alone_never_reach_the_top_band():
    # A long medical history and old age are real signals, but on their own they
    # must not outrank a fired clinical rule.
    result = assess(
        facts={"diabetes": True, "hypertension": True, "cardiac_history": True, "asthma": True},
        flags=[],
        age=80,
        waited_minutes=200,
    )
    assert result.level is not PriorityLevel.PRIORITY


def test_frail_limited_patient_outranks_young_patient_with_a_soft_flag():
    frail = assess(
        facts={"severe_limitation": True, "poor_intake": True, "worsening": True, "diabetes": True},
        flags=[],
        age=79,
        waited_minutes=40,
    )
    young = assess(facts={"syncope": True}, flags=[REVIEW_FLAG], age=24, waited_minutes=10)
    assert frail.score > young.score


def test_routine_followup_scores_near_zero():
    result = assess(facts={"diabetes": True, "hypertension": True}, flags=[], age=52, waited_minutes=0)
    assert result.level is PriorityLevel.NORMAL


def test_waiting_raises_the_score_but_is_capped():
    short = assess(facts={}, flags=[], age=30, waited_minutes=0)
    long = assess(facts={}, flags=[], age=30, waited_minutes=600)
    assert long.score > short.score
    assert long.score - short.score <= 12, "waiting must never overtake acuity"


def test_a_fired_priority_rule_is_never_demoted_by_arithmetic():
    result = assess(facts={}, flags=[PRIORITY_FLAG], age=None, waited_minutes=0)
    assert result.level is PriorityLevel.PRIORITY


def test_every_factor_is_explainable():
    result = assess(
        facts={"severe_limitation": True, "diabetes": True},
        flags=[PRIORITY_FLAG],
        age=70,
        waited_minutes=30,
    )
    assert result.factors
    for factor in result.factors:
        assert factor.label and factor.points > 0
    assert result.rationale.endswith(".")


def test_rationale_uses_no_diagnostic_or_urgency_language():
    result = assess(
        facts={"severe_limitation": True, "worsening": True},
        flags=[PRIORITY_FLAG],
        age=70,
        waited_minutes=30,
    )
    text = " ".join(f.label for f in result.factors).lower()
    for banned in ("critical", "emergency", "urgent", "likely", "severe case", "deteriorating"):
        assert banned not in text
