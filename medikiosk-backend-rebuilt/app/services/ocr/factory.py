from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ocr.base import OCRService
from app.services.ocr.mock_adapter import MockOCRService

log = get_logger(__name__)


@lru_cache
def get_ocr_service() -> OCRService:
    if settings.OCR_PROVIDER == "tesseract":
        try:
            from app.services.ocr.tesseract_adapter import TesseractOCRService

            return TesseractOCRService()
        except Exception as exc:  # noqa: BLE001
            log.error("Tesseract unavailable, using mock OCR", extra={"extra": {"error": str(exc)[:200]}})
    return MockOCRService()
