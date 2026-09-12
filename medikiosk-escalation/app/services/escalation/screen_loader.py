"""
Loads the safety screen.

Deliberately kept out of `pathways/` and loaded by hand. `load_pathways()`
globs that directory and the complaint classifier iterates whatever it finds,
so a screen file living there could be selected as a clinical pathway for
someone whose complaint happened to match. Separate directory, separate loader,
no chance of that.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.services.questioning.schema import Pathway

SCREEN_PATH = Path(__file__).parent / "screen.json"


@lru_cache
def load_screen() -> Pathway:
    try:
        return Pathway.model_validate(json.loads(SCREEN_PATH.read_text(encoding="utf-8")))
    except Exception as exc:
        # Validated at boot by main.py's lifespan, same as the pathways.
        raise RuntimeError(f"Invalid safety screen file {SCREEN_PATH.name}: {exc}") from exc
