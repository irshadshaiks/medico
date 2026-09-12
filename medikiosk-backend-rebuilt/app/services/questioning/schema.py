"""
Pathway definition schema.

Clinical question order is data, not code. A new complaint is a new JSON file
in `pathways/` — the engine never changes. Every file is validated at import
time, so a typo takes the server down at boot rather than halfway through
someone's intake.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PATHWAY_DIR = Path(__file__).parent / "pathways"


class AskIf(BaseModel):
    """Conditional node. Asked only when an earlier answer set a given key."""

    node: str
    # Any of these structured keys being true on the referenced answer.
    any_of: list[str] = Field(default_factory=list)
    # Or the raw answer matching any of these substrings, case-insensitive.
    matches: list[str] = Field(default_factory=list)


class StructuredRule(BaseModel):
    """
    Turns a free-text answer into booleans the red-flag rules can read.

    Keeping this deterministic and here — rather than asking a model what an
    answer "means" — is what makes flag firing explainable and testable.
    """

    key: str
    keywords: list[str]

    @field_validator("keywords")
    @classmethod
    def _lower(cls, v: list[str]) -> list[str]:
        return [k.lower().strip() for k in v if k.strip()]


class PathwayNode(BaseModel):
    id: str
    category: str
    question: str
    answer_type: Literal["text", "choice", "multi_choice", "number", "duration", "boolean"] = "text"
    options: list[str] | None = None
    ask_if: AskIf | None = None
    structured: list[StructuredRule] = Field(default_factory=list)
    # Skipping is allowed for optional detail, never for a red-flag screen.
    optional: bool = False

    @field_validator("options")
    @classmethod
    def _options_present(cls, v: list[str] | None, info) -> list[str] | None:
        if info.data.get("answer_type") in {"choice", "multi_choice"} and not v:
            raise ValueError(f"node '{info.data.get('id')}' is a choice question but has no options")
        return v


class Pathway(BaseModel):
    id: str
    label: str
    # Used by the offline keyword classifier and as a sanity check on the LLM's answer.
    match_keywords: list[str] = Field(default_factory=list)
    nodes: list[PathwayNode]

    @field_validator("nodes")
    @classmethod
    def _unique_and_resolvable(cls, nodes: list[PathwayNode]) -> list[PathwayNode]:
        seen: set[str] = set()
        for node in nodes:
            if node.id in seen:
                raise ValueError(f"duplicate node id '{node.id}'")
            seen.add(node.id)
        for node in nodes:
            if node.ask_if and node.ask_if.node not in seen:
                raise ValueError(f"node '{node.id}' depends on unknown node '{node.ask_if.node}'")
        return nodes


@lru_cache
def load_pathways() -> dict[str, Pathway]:
    """Read and validate every pathway file. Cached for the process lifetime."""
    pathways: dict[str, Pathway] = {}
    if not PATHWAY_DIR.exists():
        raise RuntimeError(f"Pathway directory missing: {PATHWAY_DIR}")

    for path in sorted(PATHWAY_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            pathway = Pathway.model_validate(data)
        except Exception as exc:
            raise RuntimeError(f"Invalid pathway file {path.name}: {exc}") from exc
        if pathway.id in pathways:
            raise RuntimeError(f"Duplicate pathway id '{pathway.id}' in {path.name}")
        pathways[pathway.id] = pathway

    if "generic" not in pathways:
        raise RuntimeError("A 'generic' pathway is required as the safe fallback.")
    return pathways


def get_pathway(pathway_id: str) -> Pathway:
    pathways = load_pathways()
    return pathways.get(pathway_id) or pathways["generic"]
