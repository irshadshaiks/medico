"""
The ABDM boundary.

There is no live integration here and this file is careful not to pretend
otherwise. `MockAbdmAdapter` simulates linking and export so the shape of a
real integration is visible and testable; `RealAbdmAdapter` is a deliberately
empty stub marking exactly where accredited gateway calls would go.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AbhaLinkResult:
    abha_id: str
    simulated: bool
    message: str


class AbdmGatewayService(abc.ABC):
    name: str = "abstract"
    simulated: bool = True

    @abc.abstractmethod
    async def link_abha(self, *, full_name: str, year_of_birth: int | None, mobile: str | None) -> AbhaLinkResult: ...

    @abc.abstractmethod
    async def export_record(self, bundle_input: dict[str, Any]) -> dict[str, Any]: ...


class RealAbdmAdapter(AbdmGatewayService):
    """
    Not implemented, on purpose.

    A real adapter needs ABDM sandbox credentials, an accredited health
    information provider registration, gateway session tokens, and a consent
    artefact flow. None of that is stubbed out here, because a half-real
    integration is worse than an obviously absent one.
    """

    name = "real"
    simulated = False

    async def link_abha(self, *, full_name: str, year_of_birth: int | None, mobile: str | None) -> AbhaLinkResult:
        raise NotImplementedError("Real ABDM integration requires accredited gateway credentials.")

    async def export_record(self, bundle_input: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Real ABDM integration requires accredited gateway credentials.")
