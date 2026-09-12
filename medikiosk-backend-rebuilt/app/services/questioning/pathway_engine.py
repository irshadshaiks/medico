"""
The questioning engine.

Two responsibilities, kept strictly apart:

  * Deciding what to ask next, and what an answer means structurally. This is
    pure Python over the pathway JSON. No model is consulted, so the behaviour
    is deterministic, testable and identical on every run.
  * Making the question sound human in the patient's language. This is the only
    place the LLM is used, and if it fails the templated text is shown instead.

A model can therefore make MediKiosk read worse. It cannot make it ask the
wrong clinical question.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.core.prompts import QUESTION_PHRASING
from app.services.ai.base import AICompletionRequest
from app.services.ai.factory import get_ai_service
from app.services.questioning.schema import Pathway, PathwayNode, get_pathway

log = get_logger(__name__)

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}


@dataclass(slots=True)
class AnsweredNode:
    node_id: str
    category: str
    raw_text: str
    structured: dict[str, Any]


@dataclass(slots=True)
class NextQuestion:
    node: PathwayNode
    presented_text: str
    phrasing_source: str  # "ai" | "template"
    step_index: int
    total_steps: int


def structure_answer(node: PathwayNode, raw_text: str) -> dict[str, Any]:
    """
    Deterministic keyword mapping from free text to the booleans the red-flag
    rules read. Case-insensitive substring matching — crude, but explainable,
    which matters more here than cleverness.
    """
    lowered = raw_text.lower()
    structured: dict[str, Any] = {"_raw_length": len(raw_text)}
    for rule in node.structured:
        structured[rule.key] = any(keyword in lowered for keyword in rule.keywords)
    if node.answer_type in {"choice", "multi_choice"} and node.options:
        structured["_selected"] = [opt for opt in node.options if opt.lower() in lowered]
    return structured


def _should_ask(node: PathwayNode, answered: list[AnsweredNode]) -> bool:
    """Conditional nodes: only asked when the answer they depend on warrants it."""
    if not node.ask_if:
        return True
    source = next((a for a in answered if a.node_id == node.ask_if.node), None)
    if source is None:
        return False  # dependency unanswered — skip rather than ask out of order
    if node.ask_if.any_of and any(source.structured.get(key) for key in node.ask_if.any_of):
        return True
    if node.ask_if.matches:
        lowered = source.raw_text.lower()
        return any(m.lower() in lowered for m in node.ask_if.matches)
    return not node.ask_if.any_of


def next_node(pathway: Pathway, answered: list[AnsweredNode]) -> PathwayNode | None:
    """The next unanswered node whose condition is satisfied, in file order."""
    done = {a.node_id for a in answered}
    for node in pathway.nodes:
        if node.id in done:
            continue
        if not _should_ask(node, answered):
            continue
        return node
    return None


def progress(pathway: Pathway, answered: list[AnsweredNode]) -> tuple[int, int]:
    """Step index and a total that excludes conditional nodes not triggered."""
    applicable = [n for n in pathway.nodes if _should_ask(n, answered)]
    return len(answered), max(len(applicable), len(answered))


async def phrase_question(
    node: PathwayNode, language: str, answered: list[AnsweredNode]
) -> tuple[str, str]:
    """
    Returns (text, source). English uses the pathway text verbatim — it is
    already written for patients, and a round trip through a model only risks
    drift. Other languages go through the LLM, with the template as fallback.
    """
    if language == "en":
        return node.question, "template"

    context = "; ".join(f"{a.category}: {a.raw_text[:80]}" for a in answered[-3:]) or "nothing yet"
    ai = get_ai_service()
    response = await ai.complete(
        AICompletionRequest(
            prompt=QUESTION_PHRASING.format(
                language=LANGUAGE_NAMES.get(language, "English"),
                category=node.category,
                question=node.question,
                context=context,
            ),
            temperature=0.3,
            max_output_tokens=120,
        ),
        fallback=node.question,
    )

    text = response.text.strip().strip('"')
    # A rewrite that comes back empty, enormous, or as a paragraph is not a
    # question. Fall back rather than show it.
    if not text or len(text) > 320 or text.count("?") > 1:
        return node.question, "template"
    return text, "template" if response.degraded else "ai"


async def build_next_question(
    pathway_id: str, answered: list[AnsweredNode], language: str
) -> NextQuestion | None:
    pathway = get_pathway(pathway_id)
    node = next_node(pathway, answered)
    if node is None:
        return None
    text, source = await phrase_question(node, language, answered)
    index, total = progress(pathway, answered)
    return NextQuestion(
        node=node, presented_text=text, phrasing_source=source, step_index=index, total_steps=total
    )
