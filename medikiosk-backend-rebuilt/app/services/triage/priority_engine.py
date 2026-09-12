"""
Priority scoring.

The red-flag engine answers a binary question: did a rule fire. That is not
enough to order a queue. A 78-year-old who cannot get out of bed with no rule
match should not sit behind a 24-year-old whose single flag was a fainting
episode last week.

So this layer computes an explainable acuity score from everything intake
captured, and the queue sorts on that. Three properties matter:

  * **Deterministic.** Pure arithmetic over structured facts. Same input, same
    score, every time. No model is consulted.
  * **Explainable.** Every point is attributed to a named factor with the
    patient's own evidence. A doctor asking "why is this person third" gets a
    itemised answer, not a number.
  * **Non-clinical.** A score is a queue position, not a diagnosis and not a
    triage category. It never claims how sick anyone is, only how much of what
    the patient reported warrants being looked at sooner.

Waiting time is deliberately part of the score. Without it, a low-acuity
patient can be overtaken indefinitely, which is how a queue starves people.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models.clinical import RedFlag, Visit
from app.models.enums import PriorityLevel, Severity

# Band thresholds. Chosen so a single PRIORITY red flag alone lands in the top
# band, and no combination of soft factors can reach it without one.
BAND_PRIORITY = 45
BAND_REVIEW = 18

# Waiting contributes, but is capped so it can never overtake acuity.
WAIT_POINTS_PER_20_MIN = 1
WAIT_POINTS_MAX = 12


@dataclass(slots=True)
class Factor:
    key: str
    label: str
    points: int
    evidence: str | None = None


@dataclass(slots=True)
class PriorityAssessment:
    score: int
    level: PriorityLevel
    factors: list[Factor] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "level": self.level.value,
            "factors": [
                {"key": f.key, "label": f.label, "points": f.points, "evidence": f.evidence}
                for f in self.factors
            ],
        }

    @property
    def rationale(self) -> str:
        """One line for the queue row. Describes reports, never conclusions."""
        if not self.factors:
            return "Nothing reported during intake raised this patient's position."
        top = sorted(self.factors, key=lambda f: f.points, reverse=True)[:3]
        return "; ".join(f.label for f in top) + "."


def _t(facts: dict, key: str) -> bool:
    return bool(facts.get(key))


def assess(
    *,
    facts: dict,
    flags: list[RedFlag],
    age: int | None,
    waited_minutes: int,
    abnormal_investigations: int = 0,
) -> PriorityAssessment:
    factors: list[Factor] = []

    # ------------------------------------------------------- rule matches --
    # A fired rule dominates. Capped so three flags do not triple the score
    # into meaninglessness — two priority flags and five are both "top band".
    priority_flags = [f for f in flags if f.severity is Severity.PRIORITY]
    review_flags = [f for f in flags if f.severity is Severity.REVIEW]

    if priority_flags:
        points = min(40 + 8 * (len(priority_flags) - 1), 56)
        factors.append(
            Factor(
                "red_flag_priority",
                f"{len(priority_flags)} response{'s' if len(priority_flags) > 1 else ''} matched a priority rule",
                points,
                "; ".join(f.label for f in priority_flags[:3]),
            )
        )
    if review_flags:
        factors.append(
            Factor(
                "red_flag_review",
                f"{len(review_flags)} response{'s' if len(review_flags) > 1 else ''} matched a review rule",
                min(12 * len(review_flags), 24),
                "; ".join(f.label for f in review_flags[:3]),
            )
        )

    # ------------------------------------------------------------ function --
    # What the patient can no longer do is the single most useful non-rule
    # signal intake captures, and it is often missed in a two-minute OPD.
    if _t(facts, "severe_limitation"):
        factors.append(Factor("function_severe", "Reported being unable to carry out usual activity", 15))
    elif _t(facts, "severe_pain"):
        factors.append(Factor("function_pain", "Reported pain that prevents moving comfortably", 10))

    if _t(facts, "poor_intake"):
        factors.append(Factor("intake_poor", "Reported being almost unable to eat or drink", 10))

    # ------------------------------------------------------------ age band --
    if age is not None:
        if age >= 75:
            factors.append(Factor("age_75", "Aged 75 or over", 12))
        elif age >= 65:
            factors.append(Factor("age_65", "Aged 65 or over", 8))
        elif age <= 5:
            factors.append(Factor("age_child", "Young child", 10))

    # ---------------------------------------------------------- trajectory --
    if _t(facts, "worsening"):
        factors.append(Factor("worsening", "Reported the problem is getting worse", 6))
    if _t(facts, "onset_sudden") or _t(facts, "thunderclap"):
        factors.append(Factor("sudden_onset", "Reported the problem began suddenly", 5))
    if _t(facts, "prolonged_fever"):
        factors.append(Factor("prolonged_fever", "Reported fever lasting more than a week", 6))
    if _t(facts, "chronic_cough"):
        factors.append(Factor("chronic_cough", "Reported a cough lasting several weeks", 5))

    # -------------------------------------------------------- comorbidity --
    # Small individually; the point is accumulation, capped at 9 so a long
    # medical history alone never reaches a priority band.
    comorbid = [
        ("diabetes", "diabetes"),
        ("hypertension", "high blood pressure"),
        ("cardiac_history", "a heart condition"),
        ("asthma", "asthma"),
        ("prior_tb", "previous TB"),
    ]
    present = [label for key, label in comorbid if _t(facts, key)]
    if present:
        factors.append(
            Factor(
                "comorbidity",
                f"Reported {len(present)} long-term condition{'s' if len(present) > 1 else ''}",
                min(3 * len(present), 9),
                ", ".join(present),
            )
        )

    # ------------------------------------------------------ document signal --
    if abnormal_investigations:
        factors.append(
            Factor(
                "abnormal_results",
                f"{abnormal_investigations} uploaded result{'s' if abnormal_investigations > 1 else ''} "
                "marked outside the reference range on the report",
                min(4 * abnormal_investigations, 12),
            )
        )

    # ------------------------------------------------------------ fairness --
    wait_points = min(waited_minutes // 20 * WAIT_POINTS_PER_20_MIN, WAIT_POINTS_MAX)
    if wait_points:
        factors.append(Factor("waiting", f"Waiting {waited_minutes} minutes", wait_points))

    score = sum(f.points for f in factors)
    if score >= BAND_PRIORITY:
        level = PriorityLevel.PRIORITY
    elif score >= BAND_REVIEW:
        level = PriorityLevel.REVIEW
    else:
        level = PriorityLevel.NORMAL

    # Safety floor: a fired priority rule is never demoted by arithmetic,
    # whatever the rest of the score does.
    if priority_flags:
        level = PriorityLevel.PRIORITY

    factors.sort(key=lambda f: f.points, reverse=True)
    return PriorityAssessment(score=score, level=level, factors=factors)


def waited_minutes_for(visit: Visit) -> int:
    reference = visit.queued_at or visit.created_at
    if reference is None:
        return 0
    return max(0, int((datetime.now(UTC) - reference).total_seconds() // 60))
