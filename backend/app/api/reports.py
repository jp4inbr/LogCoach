"""Leitura do link do Warcraft Logs, lista de lutas, Magos de cada luta e pré-busca dos
eventos da luta do jogador (RF03, RF04)."""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import OptionalUserDep, SessionDep, check_plan_limit
from app.errors import UNEXPECTED_ERROR_CODE, api_error
from app.models import User
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
    SHORT_FIGHT_REASON,
    PrefetchLimitError,
    ReportNotAvailableError,
    ReportSource,
    SampleReportSource,
    SourceUnavailableError,
    get_report_source,
)
from app.wcl.client import UNAVAILABLE_MESSAGE

router = APIRouter(prefix="/reports", tags=["análises"])

ReportSourceDep = Annotated[ReportSource, Depends(get_report_source)]

# Status de cada código da fonte: do Warcraft Logs (tentar de novo depois resolve) ou nosso.
SOURCE_ERROR_STATUS = {"wcl_unavailable": 503, UNEXPECTED_ERROR_CODE: 500}

PREFETCH_LIMIT_MESSAGE = (
    "Você abriu muitas lutas em pouco tempo. Espere alguns minutos para abrir outras; "
    "a análise continua funcionando, só pode demorar um pouco mais para começar."
)


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
        # Limite de pontos, API fora do ar ou erro nosso (consulta com defeito, credencial do
        # servidor): o relatório pode estar certo, então não mandamos o usuário conferir se
        # ele é público. Código e mensagem vêm do cliente do WCL, que sabe a causa.
        status = SOURCE_ERROR_STATUS.get(exc.error_code, 503)
        raise api_error(status, exc.error_code, exc.user_message) from None


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
        if fight is None and report.stale:
            # A busca nova falhou e veio a lista guardada: não dá para dizer que a luta não
            # existe, só que o Warcraft Logs não respondeu.
            raise api_error(503, "wcl_unavailable", report.stale_message or UNAVAILABLE_MESSAGE)
    if fight is None:
        raise api_error(404, "fight_not_found", "Essa luta não existe nesse relatório.")
    # Luta subindo: a duração ainda vai crescer, então o motivo é ela estar em andamento.
    if fight.in_progress:
        raise api_error(422, "unsupported_fight", fight.unsupported_reason or IN_PROGRESS_REASON)
    # Curta só se esse é o motivo: luta de outro chefe ainda subindo tem duração parcial.
    if fight.duration_s < MIN_FIGHT_S and fight.unsupported_reason in (None, SHORT_FIGHT_REASON):
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
    # de novo, com ou sem `refresh`: o log pode ser ao vivo. Menos de 8 s depois da última
    # busca vem a lista guardada. Se a busca falhar com o WCL fora do ar e houver lista
    # guardada, ela vem com `stale` e `stale_message`; sem lista guardada, vem o erro.
    return refresh_report(source, code)


@router.get("/{code}/fights/{fight_id}/players")
def fight_players(code: str, fight_id: int, source: ReportSourceDep) -> FightPlayers:
    """Magos Arcanos da luta escolhida, com spec e item level dela. Só luta suportada."""
    report, fight = load_fight(source, code, fight_id)
    players = load_fight_players(source, report.code, fight.id)
    return FightPlayers(report_code=report.code, fight_id=fight.id, players=players)


def prefetch_client(request: Request, user: User | None) -> str | None:
    """Quem pediu a pré-busca, para o limite: a conta, ou sem login o IP do pedido.

    Atrás de um proxy reverso, `request.client.host` é o IP do proxy (todos os anônimos
    dividem o limite), a menos que o uvicorn rode com `--proxy-headers` e
    `--forwarded-allow-ips` apontando para o proxy.
    """
    if user is not None:
        return f"user:{user.id}"
    return f"ip:{request.client.host}" if request.client else None


@router.post("/{code}/fights/{fight_id}/prefetch", status_code=202)
def prefetch_fight(
    code: str,
    fight_id: int,
    data: PrefetchRequest,
    request: Request,
    session: SessionDep,
    user: OptionalUserDep,
    source: ReportSourceDep,
) -> PrefetchStatus:
    """Põe na fila os eventos da luta do jogador (~12 pontos) assim que ele fica definido na
    tela, para a análise não esperar por eles. Responde na hora, sem esperar a busca.

    Login opcional. Conta sem análises no mês não pré-busca (403 `plan_limit`); cada cliente
    tem uma pré-busca na fila (a nova tira a anterior) e no máximo `PREFETCH_LIMIT` novas
    por janela (429 `prefetch_limit`). A tela ignora esses erros: a análise busca sozinha.
    """
    check_plan_limit(session, user)
    report, fight = load_fight(source, code, fight_id)
    player = load_player(source, report, fight, data.actor_id)
    client = prefetch_client(request, user)
    try:
        status = load_report(
            _SourceCall(lambda: source.prefetch(report.code, fight.id, player.actor_id, client)),
            report.code,
        )
    except PrefetchLimitError:
        raise api_error(429, "prefetch_limit", PREFETCH_LIMIT_MESSAGE) from None
    return PrefetchStatus(status=status)
