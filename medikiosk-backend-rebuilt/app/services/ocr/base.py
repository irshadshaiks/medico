"""OCR seam: bytes in, raw text and a confidence out."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(slots=True)
class OCRResult:
    text: str
    confidence: float | None
    provider: str
    page_count: int = 1
    error: str | None = None


class OCRService(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    async def extract_text(self, data: bytes, mime_type: str, languages: str | None = None) -> OCRResult: ...
