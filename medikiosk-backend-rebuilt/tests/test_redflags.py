"""
Red-flag rule tests.

Split into two halves on purpose. Triggers must fire — a missed flag is the
worst outcome. But non-triggers must stay silent too: a queue where everything
is priority is a queue with no priority in it.
"""

from __future__ import annotations

import pytest

from app.models.enums import Severity
from app.services.redflag.rules import RULES, RULES_BY_ID


def fired(facts: dict) -> set[str]:
    return {rule.id for rule in RULES if rule.predicate(facts)}


def test_ravi_scenario_fires_priority_flag():
    """Section 11's worked example: exertional chest pain radiating to the arm."""
    facts = {
        "chest_pain": True, "exertional": True, "radiates_arm": True,
        "pressure_character": True, "diaphoresis": True,
        "diabetes": True, "hypertension": True,
    }
    result = fired(facts)
    assert "chest_exertional_radiating" in result
    assert RULES_BY_ID["chest_exertional_radiating"].severity is Severity.PRIORITY


def test_routine_followup_fires_nothing():
    facts = {"diabetes": True, "hypertension": True, "worsening": False}
    assert fired(facts) == set(), "a stable follow-up must not be flagged"


def test_mild_symptoms_do_not_false_positive():
    facts = {"fever": True, "cough": True, "onset_recent": True}
    assert fired(facts) == set()


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        ({"dyspnoea_at_rest": True}, "dyspnoea_at_rest"),
        ({"haemoptysis": True}, "haemoptysis"),
        ({"thunderclap": True}, "sudden_severe_headache"),
        ({"fever": True, "neck_stiffness": True}, "fever_neuro"),
        ({"gi_bleeding": True}, "gi_bleeding"),
        ({"obstipation": True, "vomiting": True}, "obstruction_pattern"),
        ({"chest_pain": True, "breathlessness": True}, "chest_with_breathlessness"),
    ],
)
def test_known_trigger_combinations(facts, expected):
    assert expected in fired(facts)


def test_no_rule_uses_diagnostic_language():
    """
    Section 11 forbids diagnostic wording anywhere a patient or doctor sees it.
    This asserts on the exact strings rather than trusting review.
    """
    banned = (
        "heart attack", "myocardial", "infarction", "angina", "stroke", "sepsis",
        "meningitis", "appendicitis", "cancer", "likely", "probably", "suggests",
        "consistent with", "urgent", "emergency", "immediately",
    )
    for rule in RULES:
        text = f"{rule.label} {rule.detail}".lower()
        for word in banned:
            assert word not in text, f"rule '{rule.id}' uses diagnostic or urgency wording: '{word}'"


def test_every_rule_declares_its_evidence():
    for rule in RULES:
        assert rule.evidence_keys, f"rule '{rule.id}' cannot explain itself to a doctor"
