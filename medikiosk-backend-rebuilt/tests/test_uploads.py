"""Upload validation. Renaming a file must not get it past the gate."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationFailed
from app.services.document_service import _parse_date, normalize_name, sniff_mime, validate_upload

ALLOWED = ["application/pdf", "image/jpeg", "image/png"]
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4" + b"\x00" * 64


def test_sniffs_real_content_type():
    assert sniff_mime(PNG) == "image/png"
    assert sniff_mime(PDF) == "application/pdf"
    assert sniff_mime(b"MZ\x90\x00") is None


def test_executable_renamed_as_png_is_rejected():
    with pytest.raises(ValidationFailed):
        validate_upload(b"MZ\x90\x00" + b"\x00" * 64, "image/png", 10_000_000, ALLOWED)


def test_oversized_file_is_rejected():
    with pytest.raises(ValidationFailed):
        validate_upload(PNG + b"\x00" * 5000, "image/png", 1000, ALLOWED)


def test_empty_file_is_rejected():
    with pytest.raises(ValidationFailed):
        validate_upload(b"", "image/png", 10_000_000, ALLOWED)


def test_valid_upload_returns_actual_mime():
    assert validate_upload(PDF, "application/octet-stream", 10_000_000, ALLOWED) == "application/pdf"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Tab. Metformin 500mg", "metformin 500mg"), ("METFORMIN", "metformin"), ("Cap. Amoxicillin", "amoxicillin")],
)
def test_medication_names_normalize_for_deduplication(raw, expected):
    assert normalize_name(raw) == expected


def test_partial_dates_parse_without_inventing_a_day():
    assert str(_parse_date("2026-03-14")) == "2026-03-14"
    assert str(_parse_date("2026-03")) == "2026-03-01"
    assert _parse_date("sometime last year") is None
