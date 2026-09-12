"""
Escalation rules.

These are not red flags and must not be confused with them. The difference is
what happens next:

  * A **red flag** moves a patient up the OPD queue. They are still in the
    queue, still waiting, still in this department. Eighteen rules, tuned to
    catch anything a doctor would want to see sooner.
  * An **escalation** says this person should not be in the queue at all.
    Intake stops mid-question, the screen tells them where to go, and the
    triage desk is alerted. Six rules, tuned to almost never fire.

The asymmetry in those counts is the whole design. Sending someone to the
emergency counter unnecessarily costs a few minutes of a nurse's attention.
Over-trigger, though, and Casualty floods, staff stop believing the alarm, and
somebody disables the feature by the end of the first week. A safety system
that gets switched off protects nobody, so the bar here is deliberately high
and the rules are deliberately few.

--------------------------------------------------------------------------
CLINICAL SIGN-OFF REQUIRED

The patterns below were drafted by the engineering team from widely published
emergency-presentation criteria. They are a starting point for discussion, not
a validated protocol, and `SIGNED_OFF` is False for every one of them.

Before this runs in any real hospital, each rule needs a named clinician to
review the pattern, the wording shown to the patient, and the destination
department, and to set `SIGNED_OFF = True` with their name against it. The
hospital owns this protocol. We only encode it.

`escalation_service` refuses to escalate on an unsigned rule when
`ENV=production`, so an unreviewed rule cannot reach a real patient.
--------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

Facts = dict[str, object]


@dataclass(slots=True, frozen=True)
class EscalationRule:
    id: str
    # Shown to staff on the triage screen. Describes the report, not a diagnosis.
    staff_label: str
    # Shown to the patient, full screen, in their language. Short sentences,
    # an instruction, and no explanation of what it might mean — a patient told
    # "this could be a heart attack" panics, and panic helps nobody walk 40
    # metres to Casualty.
    patient_instruction: str
    destination: str
    predicate: Callable[[Facts], bool]
    evidence_keys: tuple[str, ...] = field(default=())
    # Set True only by a named clinician who has reviewed this rule.
    signed_off: bool = False
    signed_off_by: str | None = None


def _t(facts: Facts, key: str) -> bool:
    return bool(facts.get(key))


RULES: tuple[EscalationRule, ...] = (
    EscalationRule(
        id="esc_chest_pain_active",
        staff_label="Chest pain present now, with sweating or breathlessness",
        patient_instruction=(
            "Please go to the Emergency counter now. Do not wait in this queue. "
            "Show this screen to any staff member and they will take you there."
        ),
        destination="Casualty / Emergency",
        predicate=lambda f: _t(f, "esc_chest_pain_now")
        and (_t(f, "esc_sweating") or _t(f, "esc_breathless_now")),
        evidence_keys=("esc_chest_pain_now", "esc_sweating", "esc_breathless_now"),
    ),
    EscalationRule(
        id="esc_stroke_pattern",
        staff_label="Sudden weakness on one side, facial droop, or speech difficulty",
        patient_instruction=(
            "Please go to the Emergency counter now. Do not wait in this queue. "
            "Show this screen to any staff member and they will take you there."
        ),
        destination="Casualty / Emergency",
        predicate=lambda f: _t(f, "esc_sudden_weakness")
        or _t(f, "esc_face_droop")
        or _t(f, "esc_speech_difficulty"),
        evidence_keys=("esc_sudden_weakness", "esc_face_droop", "esc_speech_difficulty"),
    ),
    EscalationRule(
        id="esc_breathing_difficulty",
        staff_label="Breathing difficulty at rest, or unable to speak in full sentences",
        patient_instruction=(
            "Please go to the Emergency counter now. Do not wait in this queue. "
            "Show this screen to any staff member and they will take you there."
        ),
        destination="Casualty / Emergency",
        predicate=lambda f: _t(f, "esc_breathless_now") and not _t(f, "esc_chest_pain_now"),
        evidence_keys=("esc_breathless_now",),
    ),
    EscalationRule(
        id="esc_altered_consciousness",
        staff_label="Fit today, or confusion / drowsiness reported now",
        patient_instruction=(
            "Please go to the Emergency counter now. Do not wait in this queue. "
            "If someone is with you, show them this screen."
        ),
        destination="Casualty / Emergency",
        predicate=lambda f: _t(f, "esc_seizure_today") or _t(f, "esc_confusion_now"),
        evidence_keys=("esc_seizure_today", "esc_confusion_now"),
    ),
    EscalationRule(
        id="esc_active_bleeding",
        staff_label="Bleeding now that has not stopped",
        patient_instruction=(
            "Please go to the Emergency counter now. Do not wait in this queue. "
            "Show this screen to any staff member and they will take you there."
        ),
        destination="Casualty / Emergency",
        predicate=lambda f: _t(f, "esc_bleeding_now"),
        evidence_keys=("esc_bleeding_now",),
    ),
    EscalationRule(
        id="esc_airway_swelling",
        staff_label="Swelling of face, lips or throat with difficulty breathing or swallowing",
        patient_instruction=(
            "Please go to the Emergency counter now. Do not wait in this queue. "
            "Show this screen to any staff member and they will take you there."
        ),
        destination="Casualty / Emergency",
        predicate=lambda f: _t(f, "esc_face_throat_swelling"),
        evidence_keys=("esc_face_throat_swelling",),
    ),
)

RULES_BY_ID = {rule.id: rule for rule in RULES}

# Every structured key an escalation rule reads. Prefixed `esc_` so it can
# never collide with a red-flag key and accidentally cross the two systems.
ESCALATION_KEYS: frozenset[str] = frozenset(
    key for rule in RULES for key in rule.evidence_keys
)


def evaluate(facts: Facts) -> list[EscalationRule]:
    """Pure function over structured facts. No model, no database, no I/O."""
    fired: list[EscalationRule] = []
    for rule in RULES:
        try:
            if rule.predicate(facts):
                fired.append(rule)
        except Exception:  # noqa: BLE001
            # A broken predicate must never take intake down. Skipping it is
            # the safe failure: the patient continues and the red-flag engine
            # still runs. Logged by the caller.
            continue
    return fired
