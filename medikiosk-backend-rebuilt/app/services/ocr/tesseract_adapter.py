"""
Tesseract adapter.

Runs inside the API container, so OCR costs nothing and adds no second service.
PDFs are rasterised with PyMuPDF; images go straight through after a light
grayscale/contrast pass, which matters for phone photos of creased paper.
"""

from __future__ import annotations

import asyncio
import io

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ocr.base import OCRResult, OCRService

log = get_logger(__name__)


class TesseractOCRService(OCRService):
    name = "tesseract"

    def __init__(self) -> None:
        import pytesseract
        from PIL import Image  # noqa: F401 - checked at construction, used below

        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        self._pytesseract = pytesseract

    def _preprocess(self, image):
        from PIL import ImageOps

        # Grayscale plus autocontrast recovers a surprising amount from a photo
        # taken under a hospital fluorescent tube.
        image = ImageOps.grayscale(image)
        return ImageOps.autocontrast(image)

    def _run_sync(self, data: bytes, mime_type: str, languages: str) -> OCRResult:
        from PIL import Image

        pages: list = []
        if mime_type == "application/pdf":
            import fitz  # PyMuPDF

            with fitz.open(stream=data, filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=200)
                    pages.append(Image.open(io.BytesIO(pix.tobytes("png"))))
        else:
            pages.append(Image.open(io.BytesIO(data)))

        texts: list[str] = []
        confidences: list[float] = []
        for page in pages:
            prepared = self._preprocess(page)
            texts.append(self._pytesseract.image_to_string(prepared, lang=languages))
            try:
                report = self._pytesseract.image_to_data(
                    prepared, lang=languages, output_type=self._pytesseract.Output.DICT
                )
                scores = [int(c) for c in report.get("conf", []) if str(c).lstrip("-").isdigit() and int(c) >= 0]
                if scores:
                    confidences.append(sum(scores) / len(scores) / 100.0)
            except Exception:  # noqa: BLE001 - confidence is a nicety, not a requirement
                pass

        return OCRResult(
            text="\n\n".join(t.strip() for t in texts if t.strip()),
            confidence=(sum(confidences) / len(confidences)) if confidences else None,
            provider=self.name,
            page_count=len(pages),
        )

    async def extract_text(self, data: bytes, mime_type: str, languages: str | None = None) -> OCRResult:
        langs = languages or settings.TESSERACT_LANGS
        try:
            return await asyncio.to_thread(self._run_sync, data, mime_type, langs)
        except Exception as exc:  # noqa: BLE001
            log.error("OCR failed", extra={"extra": {"error": str(exc)[:300]}})
            return OCRResult(text="", confidence=None, provider=self.name, error=str(exc)[:300])
