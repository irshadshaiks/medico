"""Admin utilities. Guarded by ALLOW_DEMO_SEED, which config forbids in production."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import settings
from app.core.errors import Forbidden
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed-demo", dependencies=[Depends(require_admin)])
async def seed_demo(db: AsyncSession = Depends(get_db)) -> dict:
    if not settings.ALLOW_DEMO_SEED:
        raise Forbidden("Demo seeding is disabled in this environment.")
    from scripts.seed_demo_data import seed

    result = await seed(db)
    await db.commit()
    return result
