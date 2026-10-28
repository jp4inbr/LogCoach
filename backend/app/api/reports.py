"""Leitura do link do Warcraft Logs, lista de lutas, Magos de cada luta e pré-busca dos
eventos da luta do jogador (RF03, RF04)."""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.errors import api_error
from app.schemas import (
    FightOption,
    FightPlayers,
    PlayerOption,
    PrefetchRequest,
    PrefetchStatus,
    ReportResolved,
    ReportResolveRequest,
)
from app.services.links import parse_report_code
from app.services.sources import (
    IN_PROGRESS_REASON,
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
    """A luta pedida, se ela pode ser analisada. Mesmos erros no /analyses, nos jogadores e
    na pré-busca."""
    report = load_report(source, code)
    fight = next((f for f in report.fights if f.id == fight_id), None)
    if fight is None:
        # Log ao vivo: a luta pode ter acabado depois da lista guardada. Busca a lista uma vez.
        report = refresh_report(source, code)
        fight = next((f for f in report.fights if f.id == fight_id), None)
    if fight is None:
        raise api_error(404, "fight_not_found", "Essa luta não existe nesse relatório.")
    # Luta subindo: a duração ainda vai crescer, então o motivo é ela estar em andamento.
    if fight.in_progress:
        raise api_error(422, "unsupported_fight", fight.unsupported_reason or IN_PROGRESS_REASON)
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


def load_player(
    source: ReportSource, report: ReportResolved, fight: FightOption, actor_id: int
) -> PlayerOption:
    """O Mago Arcano da luta com esse id: id de fora dela ou de outra spec dá no_arcane_mage."""
    players = load_fight_players(source, report.code, fight.id)
    player = next((p for p in players if p.actor_id == actor_id), None)
    if player is None:
        raise api_error(
            422, "no_arcane_mage", "Não achamos esse personagem entre os Magos Arcanos da luta."
        )
    return player


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
    # Colar o link, "Atualizar lutas" e a atualização automática (luta subindo) leem a lista
    # de novo, com ou sem `refresh`: o log pode ser ao vivo. Menos de 15 s depois da última
    # busca vem a lista guardada; se a busca falhar, a guardada continua no cache.
    return refresh_report(source, code)


@router.get("/{code}/fights/{fight_id}/players")
def fight_players(code: str, fight_id: int, source: ReportSourceDep) -> FightPlayers:
    """Magos Arcanos da luta escolhida, com spec e item level dela. Só luta suportada."""
    report, fight = load_fight(source, code, fight_id)
    players = load_fight_players(source, report.code, fight.id)
    return FightPlayers(report_code=report.code, fight_id=fight.id, players=players)


@router.post("/{code}/fights/{fight_id}/prefetch", status_code=202)
def prefetch_fight(
    code: str, fight_id: int, data: PrefetchRequest, source: ReportSourceDep
) -> PrefetchStatus:
    """Começa a baixar os eventos da luta do jogador (~12 pontos) assim que ele fica definido
    na tela, para a análise não esperar por eles. Responde na hora, sem esperar a busca."""
    report, fight = load_fight(source, code, fight_id)
    player = load_player(source, report, fight, data.actor_id)
    status = load_report(
        _SourceCall(lambda: source.prefetch(report.code, fight.id, player.actor_id)), report.code
    )
    return PrefetchStatus(status=status)
