"""
Routes a free-text complaint to a pathway.

Keywords are tried first: they are free, instant, cover the three demo
languages, and are right most of the time. The LLM is only asked when keywords
find nothing, and its answer is rejected unless it names a pathway that exists.
Anything ambiguous lands on `generic`, which asks the safe superset of
questions — the wrong pathway is a worse failure than a generic one.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.prompts import COMPLAINT_CLASSIFICATION
from app.services.ai.base import AICompletionRequest
from app.services.ai.factory import get_ai_service
from app.services.questioning.schema import load_pathways

log = get_logger(__name__)

GENERIC = "generic"


def classify_by_keywords(complaint: str) -> str | None:
    lowered = complaint.lower()
    scores: dict[str, int] = {}
    for pathway_id, pathway in load_pathways().items():
        if pathway_id == GENERIC:
            continue
        # Longer keyword matches win: "chest pain" should beat a stray "pain".
        hits = sum(len(k) for k in pathway.match_keywords if k in lowered)
        if hits:
            scores[pathway_id] = hits
    if not scores:
        return None
    best, second = sorted(scores.values(), reverse=True)[0], None
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if len(ordered) > 1:
        second = ordered[1][1]
    # Two complaints named at once is exactly the ambiguity `generic` is for.
    if second is not None and second >= best * 0.8:
        return None
    return ordered[0][0]


async def classify_complaint(complaint: str) -> tuple[str, str]:
    """Returns (pathway_id, how_it_was_decided)."""
    if not complaint or len(complaint.strip()) < 3:
        return GENERIC, "empty"

    keyword_match = classify_by_keywords(complaint)
    if keyword_match:
        return keyword_match, "keyword"

    allowed = sorted(load_pathways().keys())
    ai = get_ai_service()
    response = await ai.complete(
        AICompletionRequest(
            prompt=COMPLAINT_CLASSIFICATION.format(
                allowed="\n".join(f"- {p}" for p in allowed), complaint=complaint[:600]
            ),
            temperature=0.0,
            max_output_tokens=16,
        ),
        fallback=GENERIC,
    )

    candidate = response.text.strip().lower().strip(".- \n`")
    if candidate in allowed:
        return candidate, "ai" if not response.degraded else "fallback"
    log.info("Classifier returned an unknown pathway", extra={"extra": {"candidate": candidate[:40]}})
    return GENERIC, "fallback"
