"""Leitura do link do Warcraft Logs e lista de lutas (RF03, RF04)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.errors import api_error
from app.schemas import ReportResolved, ReportResolveRequest
from app.services.links import parse_report_code
from app.services.sources import (
    SAMPLE_REPORT_CODE,
    ReportNotAvailableError,
    ReportSource,
    get_report_source,
)

router = APIRouter(prefix="/reports", tags=["análises"])

ReportSourceDep = Annotated[ReportSource, Depends(get_report_source)]


def load_report(source: ReportSource, code: str) -> ReportResolved:
    try:
        return source.get_report(code)
    except ReportNotAvailableError:
        raise api_error(
            404,
            "report_not_available",
            "Não conseguimos abrir esse relatório. Confira se ele está público no Warcraft Logs. "
            f"Nesta versão alfa, só o relatório de exemplo ({SAMPLE_REPORT_CODE}) está disponível.",
        ) from None


@router.post("/resolve")
def resolve_report(data: ReportResolveRequest, source: ReportSourceDep) -> ReportResolved:
    code = parse_report_code(data.url)
    if code is None:
        raise api_error(
            422,
            "invalid_link",
            "Esse link não parece ser do Warcraft Logs. "
            "Ele deve começar com warcraftlogs.com/reports/",
        )
    return load_report(source, code)
