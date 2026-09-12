from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.services.abdm.base import AbdmGatewayService
from app.services.abdm.mock_adapter import MockAbdmAdapter


@lru_cache
def get_abdm_service() -> AbdmGatewayService:
    if settings.ABDM_PROVIDER == "real":
        from app.services.abdm.base import RealAbdmAdapter

        return RealAbdmAdapter()
    return MockAbdmAdapter()
