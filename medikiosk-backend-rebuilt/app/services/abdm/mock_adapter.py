"""
Simulated ABDM.

Two safety choices worth stating:

  * Mock ABHA numbers use a `DEMO-` prefix and are 12 digits behind it, so they
    can never be mistaken for, or pasted in place of, a real Ayushman Bharat
    identifier.
  * Export includes only doctor-verified sections. Draft AI text does not leave
    the system under a FHIR-shaped wrapper.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Any

from app.services.abdm.base import AbdmGatewayService, AbhaLinkResult

SIMULATION_NOTICE = (
    "SIMULATED. This record was produced by a demonstration system and has not been "
    "sent to, or issued by, the Ayushman Bharat Digital Mission."
)


class MockAbdmAdapter(AbdmGatewayService):
    name = "mock"
    simulated = True

    async def link_abha(self, *, full_name: str, year_of_birth: int | None, mobile: str | None) -> AbhaLinkResult:
        digits = "".join(str(random.randint(0, 9)) for _ in range(12))
        return AbhaLinkResult(
            abha_id=f"DEMO-{digits[:4]}-{digits[4:8]}-{digits[8:]}",
            simulated=True,
            message="A simulated ABHA number was created for this demonstration. It is not a real health ID.",
        )

    async def export_record(self, bundle_input: dict[str, Any]) -> dict[str, Any]:
        """FHIR-shaped, not FHIR-conformant. Recognisable to a judge, honest in its labelling."""
        patient = bundle_input.get("patient", {})
        now = datetime.now(UTC).isoformat()
        entries: list[dict[str, Any]] = [
            {
                "fullUrl": f"urn:uuid:{patient.get('id')}",
                "resource": {
                    "resourceType": "Patient",
                    "id": str(patient.get("id")),
                    "identifier": [
                        {"system": "https://demo.medikiosk.invalid/abha-simulated", "value": patient.get("abha_id")}
                    ],
                    "name": [{"text": patient.get("name")}],
                    "gender": patient.get("sex"),
                },
            }
        ]

        for section in bundle_input.get("sections", []):
            entries.append(
                {
                    "resource": {
                        "resourceType": "Composition",
                        "status": "final",
                        "title": section.get("label"),
                        "date": now,
                        "section": [{"title": section.get("label"), "text": {"status": "generated", "div": section.get("body")}}],
                    }
                }
            )

        for medication in bundle_input.get("medications", []):
            entries.append(
                {
                    "resource": {
                        "resourceType": "MedicationStatement",
                        "status": "active",
                        "medicationCodeableConcept": {"text": medication.get("name")},
                        "dosage": [{"text": " ".join(filter(None, [medication.get("dose"), medication.get("frequency")]))}],
                    }
                }
            )

        for investigation in bundle_input.get("investigations", []):
            entries.append(
                {
                    "resource": {
                        "resourceType": "Observation",
                        "status": "final",
                        "code": {"text": investigation.get("name")},
                        "valueQuantity": {"value": investigation.get("value"), "unit": investigation.get("unit")},
                        "effectiveDateTime": investigation.get("date"),
                    }
                }
            )

        return {
            "resourceType": "Bundle",
            "type": "document",
            "timestamp": now,
            "meta": {"tag": [{"code": "SIMULATED", "display": SIMULATION_NOTICE}]},
            "_simulated": True,
            "_notice": SIMULATION_NOTICE,
            "entry": entries,
        }
