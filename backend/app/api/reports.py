"""Leitura do link do Warcraft Logs, lista de lutas e Magos de cada luta (RF03, RF04)."""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.errors import api_error
from app.schemas import (
    FightOption,
    FightPlayers,
    PlayerOption,
    ReportResolved,
    ReportResolveRequest,
)
from app.services.links import parse_report_code
from app.services.sources import (
    MIN_FIGHT_S,
    SAMPLE_REPORT_CODE,
    ReportNotAvailableError,
    ReportSource,
    SampleReportSource,
    SourceUnavailableError,
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
    except SourceUnavailableError as exc:
        # Limite de pontos, API fora do ar ou credencial do servidor: o relatório pode estar
        # certo, então não mandamos o usuário conferir se ele é público. A mensagem vem do
        # cliente do WCL, que sabe a causa.
        raise api_error(503, "wcl_unavailable", exc.user_message) from None


class _SourceCall:
    """Faz outra chamada da fonte passar pelo `load_report`, o único lugar que traduz os
    erros da fonte para a resposta (mesmos códigos e mensagens)."""

    def __init__(self, call: Callable[[], Any]) -> None:
        self._call = call

    def get_report(self, code: str) -> Any:
        return self._call()


def refresh_report(source: ReportSource, code: str) -> ReportResolved:
    if isinstance(source, SampleReportSource):
        return load_report(source, code)  # o exemplo não tem lutas novas
    return load_report(_SourceCall(lambda: source.get_report(code, refresh=True)), code)


def load_fight(
    source: ReportSource, code: str, fight_id: int
) -> tuple[ReportResolved, FightOption]:
    """A luta pedida, se ela pode ser analisada. Mesmos erros no /analyses e nos jogadores."""
    report = load_report(source, code)
    fight = next((f for f in report.fights if f.id == fight_id), None)
    if fight is None:
        # Log ao vivo: a luta pode ter acabado depois da lista guardada. Busca a lista uma vez.
        report = refresh_report(source, code)
        fight = next((f for f in report.fights if f.id == fight_id), None)
    if fight is None:
        raise api_error(404, "fight_not_found", "Essa luta não existe nesse relatório.")
    if fight.duration_s < MIN_FIGHT_S:
        raise api_error(
            422, "fight_too_short", "A luta tem menos de 60 s. Escolha uma tentativa mais longa."
        )
    if not fight.supported:
        raise api_error(
            422, "unsupported_fight", fight.unsupported_reason or "Chefe ainda não suportado."
        )
    return report, fight


def load_fight_players(source: ReportSource, code: str, fight_id: int) -> list[PlayerOption]:
    return load_report(_SourceCall(lambda: source.get_fight_players(code, fight_id)), code)


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
    # "Atualizar lutas" (log ao vivo): lê a lista de novo; o cache só muda se der certo.
    if data.refresh:
        return refresh_report(source, code)
    return load_report(source, code)


@router.get("/{code}/fights/{fight_id}/players")
def fight_players(code: str, fight_id: int, source: ReportSourceDep) -> FightPlayers:
    """Magos Arcanos da luta escolhida, com spec e item level dela. Só luta suportada."""
    report, fight = load_fight(source, code, fight_id)
    players = load_fight_players(source, report.code, fight.id)
    return FightPlayers(report_code=report.code, fight_id=fight.id, players=players)
