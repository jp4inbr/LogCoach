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
    SampleReportSource,
    get_report_source,
)

router = APIRouter(prefix="/reports", tags=["análises"])

ReportSourceDep = Annotated[ReportSource, Depends(get_report_source)]


def load_report(source: ReportSource, code: str) -> ReportResolved:
    try:
        return source.get_report(code)
    except ReportNotAvailableError:
        message = (
            "Não conseguimos abrir esse relatório. Confira se ele está público no Warcraft Logs."
        )
        if isinstance(source, SampleReportSource):
            # Modo offline (DATA_SOURCE=exemplo): só o relatório de exemplo existe.
            message += (
                " Sem conexão com o Warcraft Logs, só o relatório de exemplo "
                f"({SAMPLE_REPORT_CODE}) está disponível."
            )
        raise api_error(404, "report_not_available", message) from None


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
