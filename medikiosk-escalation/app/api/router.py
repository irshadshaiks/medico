from __future__ import annotations

from fastapi import APIRouter

from app.api import abdm, admin, auth, doctor, documents, escalation, patient, privacy

api_router = APIRouter()
api_router.include_router(auth.router)
# Registered before patient routes: the safety screen precedes intake.
api_router.include_router(escalation.router)
api_router.include_router(patient.router)
api_router.include_router(documents.router)
api_router.include_router(doctor.router)
api_router.include_router(privacy.router)
api_router.include_router(abdm.router)
api_router.include_router(admin.router)
