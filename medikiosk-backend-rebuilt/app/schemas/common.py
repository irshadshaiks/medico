"""Shared response envelopes."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class AuditEntry(ORMModel):
    id: uuid.UUID
    event: str
    actor_id: uuid.UUID | None
    actor_role: str | None
    summary: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime
