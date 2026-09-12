"""
Escalation tests.

Two properties matter more than anything else here, and they pull in opposite
directions:

  * A genuine emergency presentation must stop the interview. Missing one is
    the failure the evaluator was pointing at.
  * An ordinary OPD complaint must not. Over-triggering floods Casualty, staff
    stop believing the alarm, and somebody disables the feature — at which
    point the first property is worth nothing.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.services.escalation.rules import ESCALATION_KEYS, RULES, evaluate


def fired(facts: dict) -> set[str]:
    return {rule.id for rule in evaluate(facts)}


# ------------------------------------------------------------ must escalate --


@pytest.mark.parametrize(
    ("label", "facts", "expected"),
    [
        ("chest pain now with sweating",
         {"esc_chest_pain_now": True, "esc_sweating": True}, "esc_chest_pain_active"),
        ("chest pain now with breathlessness",
         {"esc_chest_pain_now": True, "esc_breathless_now": True}, "esc_chest_pain_active"),
        ("sudden one-sided weakness",
         {"esc_sudden_weakness": True}, "esc_stroke_pattern"),
        ("facial droop", {"esc_face_droop": True}, "esc_stroke_pattern"),
        ("breathless at rest, no chest pain",
         {"esc_breathless_now": True}, "esc_breathing_difficulty"),
        ("fit today", {"esc_seizure_today": True}, "esc_altered_consciousness"),
        ("bleeding that will not stop", {"esc_bleeding_now": True}, "esc_active_bleeding"),
        ("throat swelling", {"esc_face_throat_swelling": True}, "esc_airway_swelling"),
    ],
)
def test_emergency_presentations_escalate(label, facts, expected):
    assert expected in fired(facts), label


# -------------------------------------------------------- must NOT escalate --


@pytest.mark.parametrize(
    ("label", "facts"),
    [
        ("Ravi: exertional chest pain, settled now — a red flag, not an escalation",
         {"chest_pain": True, "exertional": True, "radiates_arm": True,
          "diaphoresis": True, "diabetes": True, "ongoing_now": False}),
        ("stable diabetes follow-up", {"diabetes": True, "hypertension": True}),
        ("fever and cough for three days", {"fever": True, "cough": True}),
        ("knee pain six months", {"worsening": True}),
        ("headache six weeks, vision blurring", {"visual_disturbance": True, "morning_headache": True}),
        ("fainting last week", {"syncope": True}),
        ("breathless only on exertion", {"dyspnoea_minimal_exertion": True}),
        ("empty intake", {}),
    ],
)
def test_ordinary_opd_complaints_do_not_escalate(label, facts):
    assert fired(facts) == set(), f"false escalation on: {label}"


def test_red_flag_keys_cannot_trigger_an_escalation():
    """
    The two engines share one facts dict. Every escalation key is `esc_`
    prefixed precisely so a red-flag key can never reach an escalation rule.
    """
    red_flag_facts = {
        "chest_pain": True, "exertional": True, "radiates_arm": True, "breathlessness": True,
        "diaphoresis": True, "thunderclap": True, "gi_bleeding": True, "haemoptysis": True,
        "altered_consciousness": True, "seizure": True, "uncontrolled_bleeding": True,
        "dyspnoea_at_rest": True, "fever": True, "neck_stiffness": True,
    }
    assert fired(red_flag_facts) == set()
    assert all(key.startswith("esc_") for key in ESCALATION_KEYS)


# ------------------------------------------------------------------ safety --


def test_every_rule_is_marked_unsigned_until_a_clinician_reviews_it():
    for rule in RULES:
        assert rule.signed_off is False, (
            f"rule '{rule.id}' claims clinical sign-off. Set this only with a named clinician."
        )


def test_patient_instruction_never_names_a_condition():
    banned = (
        "heart attack", "myocardial", "infarction", "stroke", "cardiac", "anaphylaxis",
        "sepsis", "haemorrhage", "may be", "could be", "likely", "serious", "critical",
        "life-threatening", "dying",
    )
    for rule in RULES:
        text = rule.patient_instruction.lower()
        for word in banned:
            assert word not in text, f"rule '{rule.id}' tells the patient what might be wrong: '{word}'"


def test_patient_instruction_gives_a_destination_and_an_action():
    for rule in RULES:
        text = rule.patient_instruction.lower()
        assert "emergency" in text
        assert "do not wait" in text or "now" in text
        assert rule.destination


def test_rule_set_stays_small():
    # Six rules is a design constraint, not an accident. Growing this set is
    # how the alarm stops being believed.
    assert len(RULES) <= 8, "escalation rule set is growing; every addition raises the false-positive rate"


def test_a_broken_predicate_fails_open():
    from app.services.escalation.rules import EscalationRule

    exploding = EscalationRule(
        id="boom", staff_label="x", patient_instruction="Please go to the Emergency counter now.",
        destination="Casualty", predicate=lambda f: 1 / 0,  # noqa: ARG005
    )
    import app.services.escalation.rules as module

    original = module.RULES
    module.RULES = (*original, exploding)
    try:
        # The broken rule is skipped; the working ones still evaluate.
        assert "esc_active_bleeding" in fired({"esc_bleeding_now": True})
    finally:
        module.RULES = original


# ------------------------------------------------------------------ screen --


def test_every_screen_option_maps_to_a_rule_key():
    """
    A danger option a patient can tap that maps to no structured key is a
    silent failure: the patient reports an emergency and nothing happens.
    """
    path = pathlib.Path("app/services/escalation/screen.json")
    node = json.loads(path.read_text())["nodes"][0]
    options = [o.lower() for o in node["options"]]

    for rule in node["structured"]:
        assert rule["key"].startswith("esc_")
        assert any(kw in option for kw in rule["keywords"] for option in options), (
            f"structured key '{rule['key']}' matches none of the presented options"
        )

    # Every option except the opt-out must produce a key.
    danger_options = [o for o in options if "none of these" not in o]
    for option in danger_options:
        assert any(kw in option for rule in node["structured"] for kw in rule["keywords"]), (
            f"option '{option}' maps to no structured key"
        )


def test_screen_keys_are_all_consumed_by_a_rule():
    path = pathlib.Path("app/services/escalation/screen.json")
    node = json.loads(path.read_text())["nodes"][0]
    screen_keys = {r["key"] for r in node["structured"]}
    assert screen_keys == set(ESCALATION_KEYS), (
        f"screen and rules disagree: only in screen {screen_keys - set(ESCALATION_KEYS)}, "
        f"only in rules {set(ESCALATION_KEYS) - screen_keys}"
    )
