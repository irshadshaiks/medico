"""
Red-flag rules.

Every rule is a plain predicate over the structured booleans the pathway engine
produced. No model participates in the decision. That is deliberate: a flag
here changes where a patient sits in the queue, and a doctor asked "why is this
person at the top" must get a specific, reproducible answer — which rule, and
which of the patient's own words triggered it.

Wording discipline: `label` and `detail` describe what the patient reported.
They never name a condition, never rank likelihood, and never say how urgent
something is. `severity` orders the queue; it is not a clinical judgement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.models.enums import Severity

# Structured keys, merged across every answer in the conversation.
Facts = dict[str, object]


@dataclass(slots=True, frozen=True)
class RedFlagRule:
    id: str
    label: str
    detail: str
    severity: Severity
    predicate: Callable[[Facts], bool]
    # Which structured keys made it fire — shown to the doctor as evidence.
    evidence_keys: tuple[str, ...] = field(default=())


def _t(facts: Facts, key: str) -> bool:
    return bool(facts.get(key))


RULES: tuple[RedFlagRule, ...] = (
    # ------------------------------------------------------------- cardiac --
    RedFlagRule(
        id="chest_exertional_radiating",
        label="Chest discomfort on exertion, spreading from the chest",
        detail=(
            "The patient reported chest discomfort brought on by physical activity, "
            "and said the feeling travels away from the chest."
        ),
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "exertional")
        and (_t(f, "radiates_arm") or _t(f, "radiates_jaw")),
        evidence_keys=("exertional", "radiates_arm", "radiates_jaw"),
    ),
    RedFlagRule(
        id="chest_with_breathlessness",
        label="Chest discomfort with breathlessness",
        detail="The patient reported chest discomfort and breathlessness occurring together.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "chest_pain") and _t(f, "breathlessness"),
        evidence_keys=("chest_pain", "breathlessness"),
    ),
    RedFlagRule(
        id="chest_pressure_with_sweating",
        label="Chest pressure with sweating",
        detail="The patient described the chest sensation as pressure or heaviness, with sweating during episodes.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "pressure_character") and _t(f, "diaphoresis"),
        evidence_keys=("pressure_character", "diaphoresis"),
    ),
    RedFlagRule(
        id="chest_prolonged_ongoing",
        label="Chest discomfort present now and prolonged",
        detail="The patient reported the chest discomfort has lasted more than twenty minutes and is present during intake.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "prolonged_episode") and _t(f, "ongoing_now"),
        evidence_keys=("prolonged_episode", "ongoing_now"),
    ),
    RedFlagRule(
        id="cardiac_risk_context",
        label="Chest symptoms alongside recorded risk factors",
        detail="Chest symptoms were reported by a patient who also reported diabetes, high blood pressure, or a heart condition.",
        severity=Severity.REVIEW,
        predicate=lambda f: (_t(f, "chest_pain") or _t(f, "pressure_character") or _t(f, "exertional"))
        and (_t(f, "diabetes") or _t(f, "hypertension") or _t(f, "cardiac_history")),
        evidence_keys=("diabetes", "hypertension", "cardiac_history"),
    ),
    # ----------------------------------------------------------- breathing --
    RedFlagRule(
        id="dyspnoea_at_rest",
        label="Breathlessness at rest",
        detail="The patient reported becoming breathless without any exertion.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "dyspnoea_at_rest"),
        evidence_keys=("dyspnoea_at_rest",),
    ),
    RedFlagRule(
        id="haemoptysis",
        label="Blood reported in phlegm",
        detail="The patient reported coughing up blood or blood-stained phlegm.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "haemoptysis"),
        evidence_keys=("haemoptysis",),
    ),
    RedFlagRule(
        id="chronic_cough_weight_loss",
        label="Long-standing cough with weight loss",
        detail="The patient reported a cough lasting several weeks together with weight loss or night sweats.",
        severity=Severity.REVIEW,
        predicate=lambda f: _t(f, "chronic_cough") and (_t(f, "weight_loss") or _t(f, "night_sweats")),
        evidence_keys=("chronic_cough", "weight_loss", "night_sweats"),
    ),
    # ---------------------------------------------------------- neurologic --
    RedFlagRule(
        id="sudden_severe_headache",
        label="Headache described as sudden in onset",
        detail="The patient reported the headache began suddenly and at full intensity.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "thunderclap"),
        evidence_keys=("thunderclap",),
    ),
    RedFlagRule(
        id="headache_focal_signs",
        label="Headache with weakness or vision change",
        detail="The patient reported weakness on one side, or a change in vision, alongside the headache.",
        severity=Severity.PRIORITY,
        predicate=lambda f: (_t(f, "focal_weakness") or _t(f, "visual_disturbance"))
        and not _t(f, "chest_pain"),
        evidence_keys=("focal_weakness", "visual_disturbance"),
    ),
    RedFlagRule(
        id="fever_neuro",
        label="Fever with neck stiffness or confusion",
        detail="The patient reported fever together with neck stiffness, confusion, or a fit.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "fever")
        and (_t(f, "neck_stiffness") or _t(f, "altered_consciousness") or _t(f, "seizure")),
        evidence_keys=("fever", "neck_stiffness", "altered_consciousness", "seizure"),
    ),
    RedFlagRule(
        id="altered_consciousness",
        label="Confusion or a fit reported",
        detail="The patient or their attendant reported confusion, drowsiness, or a fit.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "altered_consciousness") or _t(f, "seizure"),
        evidence_keys=("altered_consciousness", "seizure"),
    ),
    RedFlagRule(
        id="syncope",
        label="Fainting reported",
        detail="The patient reported fainting or blacking out.",
        severity=Severity.REVIEW,
        predicate=lambda f: _t(f, "syncope"),
        evidence_keys=("syncope",),
    ),
    # ----------------------------------------------------------- abdominal --
    RedFlagRule(
        id="gi_bleeding",
        label="Blood reported in vomit or stool",
        detail="The patient reported blood in vomit, or black or bloody stool.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "gi_bleeding"),
        evidence_keys=("gi_bleeding",),
    ),
    RedFlagRule(
        id="obstruction_pattern",
        label="Abdominal pain with vomiting and nothing passed",
        detail="The patient reported abdominal pain with vomiting and has not passed stool or gas.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "obstipation") and _t(f, "vomiting"),
        evidence_keys=("obstipation", "vomiting"),
    ),
    RedFlagRule(
        id="severe_sudden_abdominal",
        label="Sudden, severe abdominal pain",
        detail="The patient reported abdominal pain that began suddenly and prevents them from moving comfortably.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "onset_sudden") and _t(f, "severe_pain"),
        evidence_keys=("onset_sudden", "severe_pain"),
    ),
    # --------------------------------------------------------------- other --
    RedFlagRule(
        id="uncontrolled_bleeding",
        label="Bleeding that would not stop",
        detail="The patient reported bleeding that did not stop on its own.",
        severity=Severity.PRIORITY,
        predicate=lambda f: _t(f, "uncontrolled_bleeding"),
        evidence_keys=("uncontrolled_bleeding",),
    ),
    RedFlagRule(
        id="poor_intake_prolonged_fever",
        label="Prolonged fever with almost no food or fluid",
        detail="The patient reported fever lasting more than a week and being almost unable to eat or drink.",
        severity=Severity.REVIEW,
        predicate=lambda f: _t(f, "prolonged_fever") and _t(f, "poor_intake"),
        evidence_keys=("prolonged_fever", "poor_intake"),
    ),
)


RULES_BY_ID = {rule.id: rule for rule in RULES}
