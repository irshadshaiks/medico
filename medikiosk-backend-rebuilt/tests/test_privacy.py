"""
Insider-misuse control tests.

The threat model is a legitimate account reading or exporting records it has no
clinical relationship with. These assert the controls that make that expensive
and visible.
"""

from __future__ import annotations

import uuid

import pytest

from app.services.privacy.access_guard import (
    BULK_DISTINCT_PATIENTS,
    EXPORT_THRESHOLD,
    MIN_JUSTIFICATION,
    watermark_for,
)


def test_watermarks_are_unique_per_export():
    actor, patient = uuid.uuid4(), uuid.uuid4()
    marks = {watermark_for(actor, patient) for _ in range(200)}
    assert len(marks) == 200, "a reused watermark would make a leak untraceable"


def test_watermark_does_not_leak_the_patient_id():
    actor, patient = uuid.uuid4(), uuid.uuid4()
    mark = watermark_for(actor, patient)
    assert str(patient) not in mark
    assert str(patient).replace("-", "") not in mark.lower()


def test_watermark_is_recognisable_and_bounded():
    mark = watermark_for(uuid.uuid4(), uuid.uuid4())
    assert mark.startswith("MK-")
    assert len(mark) <= 64, "must fit the receipt column"


def test_thresholds_are_set_above_plausible_clinical_workload():
    # A doctor seeing 60 patients in a session opens roughly one record every
    # two minutes. The bulk threshold must sit well above that or it will fire
    # on ordinary work and be switched off.
    assert BULK_DISTINCT_PATIENTS >= 20
    assert EXPORT_THRESHOLD >= 5
    assert MIN_JUSTIFICATION >= 10
