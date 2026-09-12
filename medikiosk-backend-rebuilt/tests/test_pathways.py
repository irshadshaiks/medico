"""
Pathway and questioning-engine tests.

These are the ones that matter most: they cover the logic that decides what a
patient is asked, which is the part where a regression is a clinical problem
rather than a cosmetic one.
"""

from __future__ import annotations

import pytest

from app.services.questioning.pathway_engine import (
    AnsweredNode,
    next_node,
    progress,
    structure_answer,
)
from app.services.questioning.schema import get_pathway, load_pathways


def test_every_pathway_file_validates():
    # Module 18 requires malformed pathway files to be caught at startup.
    pathways = load_pathways()
    assert "generic" in pathways
    for pathway_id in ("chest_pain", "fever", "abdominal_pain", "respiratory", "headache"):
        assert pathway_id in pathways, f"{pathway_id} pathway is missing"
        assert pathways[pathway_id].nodes


def test_unknown_pathway_falls_back_to_generic():
    assert get_pathway("cardiology_subspecialty_workup").id == "generic"


def test_pathway_walks_nodes_in_file_order():
    pathway = get_pathway("chest_pain")
    answered: list[AnsweredNode] = []
    seen: list[str] = []

    for _ in range(len(pathway.nodes) + 2):
        node = next_node(pathway, answered)
        if node is None:
            break
        seen.append(node.id)
        answered.append(AnsweredNode(node.id, node.category, "no", structure_answer(node, "no")))

    assert seen[0] == "site"
    assert next_node(pathway, answered) is None, "pathway should reach completion"
    # 'exertion_detail' is conditional and must not appear when nothing triggered it.
    assert "exertion_detail" not in seen


def test_conditional_node_appears_only_when_triggered():
    pathway = get_pathway("chest_pain")
    aggravating = next(n for n in pathway.nodes if n.id == "aggravating")

    answered = [
        AnsweredNode(n.id, n.category, "no", structure_answer(n, "no"))
        for n in pathway.nodes
        if n.id in {"site", "character", "onset", "duration_episode"}
    ]
    answered.append(
        AnsweredNode(
            "aggravating", "aggravating_factors",
            "It comes when I climb stairs",
            structure_answer(aggravating, "It comes when I climb stairs"),
        )
    )

    remaining: list[str] = []
    working = list(answered)
    for _ in range(len(pathway.nodes)):
        node = next_node(pathway, working)
        if node is None:
            break
        remaining.append(node.id)
        working.append(AnsweredNode(node.id, node.category, "no", structure_answer(node, "no")))

    assert "exertion_detail" in remaining


def test_structure_answer_maps_keywords_to_booleans():
    pathway = get_pathway("chest_pain")
    node = next(n for n in pathway.nodes if n.id == "associated")

    structured = structure_answer(node, "I was sweating a lot and could not breathe")
    assert structured["diaphoresis"] is True
    assert structured["breathlessness"] is True
    assert structured["nausea"] is False


def test_structure_answer_handles_transliterated_input():
    pathway = get_pathway("generic")
    node = next(n for n in pathway.nodes if n.id == "associated")
    assert structure_answer(node, "mujhe bukhar hai")["fever"] is True


def test_progress_excludes_untriggered_conditional_nodes():
    pathway = get_pathway("chest_pain")
    index, total = progress(pathway, [])
    assert index == 0
    assert total < len(pathway.nodes), "conditional nodes should not inflate the progress bar"
