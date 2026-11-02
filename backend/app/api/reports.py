"""Leitura do link do Warcraft Logs, lista de lutas, Magos de cada luta e pré-busca dos
eventos da luta do jogador (RF03, RF04)."""

import ipaddress
from collections.abc import Callable, Hashable
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
from app.services.links import is_classic_link, parse_report_code
from app.services.sources import (
    IN_PROGRESS_REASON,
    MIN_FIGHT_S,
    QUERY_LIMIT_CODE,
    SAMPLE_REPORT_CODE,
    SHORT_FIGHT_REASON,
    UPLOAD_PAUSED_REASON,
    FightNotFoundError,
    PlayerNotFoundError,
    PrefetchLimitError,
    QueryLimitError,
    ReportNotAvailableError,
    ReportSource,
    SampleReportSource,
    SourceUnavailableError,
    get_report_source,
)
from app.wcl.client import UNAVAILABLE_MESSAGE, WCL_UNAVAILABLE_CODE

router = APIRouter(prefix="/reports", tags=["análises"])

ReportSourceDep = Annotated[ReportSource, Depends(get_report_source)]

# Status de cada código da fonte: do Warcraft Logs (tentar de novo depois resolve), nosso, ou
# o limite de consultas do cliente.
SOURCE_ERROR_STATUS = {WCL_UNAVAILABLE_CODE: 503, UNEXPECTED_ERROR_CODE: 500, QUERY_LIMIT_CODE: 429}

PREFETCH_LIMIT_MESSAGE = (
    "Você abriu muitas lutas em pouco tempo. Espere alguns minutos para abrir outras; "
    "a análise continua funcionando, só pode demorar um pouco mais para começar."
)
INVALID_LINK_MESSAGE = (
    "Esse link não parece ser do Warcraft Logs. Ele deve começar com warcraftlogs.com/reports/"
)
CLASSIC_LINK_MESSAGE = (
    "Esse link é do Warcraft Logs Classic. O LogCoach analisa só logs do World of Warcraft atual."
)
ARCHIVED_MESSAGE = (
    "Esse relatório foi arquivado no Warcraft Logs e não pode mais ser lido pela API. "
    "Peça para quem enviou reativá-lo ou use um log mais recente."
)
FIGHT_NOT_FOUND_MESSAGE = "Essa luta não existe nesse relatório."
NO_ARCANE_MAGE_MESSAGE = "Não achamos esse personagem entre os Magos Arcanos da luta."


def load_report(source: ReportSource, code: str, client: Hashable | None = None) -> ReportResolved:
    """A lista de lutas, traduzindo os erros da fonte para a resposta. As outras chamadas da
    fonte passam por aqui com `_SourceCall` (mesmos códigos e mensagens em todas as rotas)."""
    try:
        return source.get_report(code, client=client)
    except QueryLimitError as exc:
        raise api_error(429, QUERY_LIMIT_CODE, exc.user_message) from None
    except FightNotFoundError:
        raise api_error(404, "fight_not_found", FIGHT_NOT_FOUND_MESSAGE) from None
    except PlayerNotFoundError:
        raise api_error(422, "no_arcane_mage", NO_ARCANE_MAGE_MESSAGE) from None
    except ReportNotAvailableError as exc:
        if exc.archived:
            raise api_error(404, "report_not_available", ARCHIVED_MESSAGE) from None
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

    def get_report(self, code: str, client: Hashable | None = None) -> Any:
        return self._call()


def refresh_report(
    source: ReportSource, code: str, client: Hashable | None = None
) -> ReportResolved:
    if isinstance(source, SampleReportSource):
        return load_report(source, code, client)  # o exemplo não tem lutas novas
    return load_report(
        _SourceCall(lambda: source.get_report(code, refresh=True, client=client)), code
    )


def _find(report: ReportResolved, fight_id: int) -> FightOption | None:
    return next((f for f in report.fights if f.id == fight_id), None)


def load_fight(
    source: ReportSource, code: str, fight_id: int, client: Hashable | None = None
) -> tuple[ReportResolved, FightOption]:
    """A luta pedida, se ela pode ser analisada. Mesmos erros no /analyses, nos jogadores e
    na pré-busca. `client` conta no limite de consultas quando a lista vai à API."""
    report = load_report(source, code, client)
    fight = _find(report, fight_id)
    refreshed = False
    if fight is None:
        # Log ao vivo: a luta pode ter acabado depois da lista guardada. Busca a lista uma vez.
        report = refresh_report(source, code, client)
        refreshed = True
        fight = _find(report, fight_id)
        if fight is None and report.stale:
            # A busca nova falhou e veio a lista guardada: não dá para dizer que a luta não
            # existe, só repassar o erro da busca (mesmo status e código do `load_report`).
            error_code = report.stale_code or WCL_UNAVAILABLE_CODE
            raise api_error(
                SOURCE_ERROR_STATUS.get(error_code, 503),
                error_code,
                report.stale_message or UNAVAILABLE_MESSAGE,
            )
    if fight is None:
        raise api_error(404, "fight_not_found", FIGHT_NOT_FOUND_MESSAGE)
    if (fight.in_progress or fight.upload_paused) and not refreshed:
        # A lista guardada pode ser de quando a luta ainda subia (ou o envio estava parado):
        # busca uma vez antes de recusar. A trava de 8 s e a pausa depois de falha evitam gasto.
        report = refresh_report(source, code, client)
        fight = _find(report, fight_id) or fight
    # Luta subindo: a duração ainda vai crescer, então o motivo é ela estar em andamento.
    if fight.in_progress:
        raise api_error(422, "unsupported_fight", fight.unsupported_reason or IN_PROGRESS_REASON)
    if fight.upload_paused:
        raise api_error(422, "unsupported_fight", UPLOAD_PAUSED_REASON)
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


def load_fight_players(
    source: ReportSource, code: str, fight_id: int, client: Hashable | None = None
) -> list[PlayerOption]:
    return load_report(
        _SourceCall(lambda: source.get_fight_players(code, fight_id, client=client)), code
    )


def load_player(
    source: ReportSource,
    report: ReportResolved,
    fight: FightOption,
    actor_id: int,
    client: Hashable | None = None,
) -> PlayerOption:
    """O Mago Arcano da luta com esse id: id de fora dela ou de outra spec dá no_arcane_mage."""
    players = load_fight_players(source, report.code, fight.id, client)
    player = next((p for p in players if p.actor_id == actor_id), None)
    if player is None:
        raise api_error(422, "no_arcane_mage", NO_ARCANE_MAGE_MESSAGE)
    return player


def request_client(request: Request, user: User | None) -> str | None:
    """Quem fez o pedido, para os limites (consultas ao WCL e pré-busca): a conta, ou sem
    login o IP do pedido.

    IPv6 conta pela rede /64: um provedor dá a cada casa um /64 inteiro, e trocar de
    endereço dentro dele não pode zerar o limite. Atrás de um proxy reverso,
    `request.client.host` é o IP do proxy (todos os anônimos dividem o limite), a menos que
    o uvicorn rode com `--proxy-headers` e `--forwarded-allow-ips` apontando para o proxy.
    """
    if user is not None:
        return f"user:{user.id}"
    if not request.client:
        return None
    host = request.client.host
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return f"ip:{host}"  # não é IP (cliente de teste, socket local)
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return f"ip:{ip.ipv4_mapped}"  # ::ffff:1.2.3.4 é o IPv4 de sempre
        return f"ip:{ipaddress.IPv6Network((ip, 64), strict=False)}"
    return f"ip:{ip}"


@router.post("/resolve")
def resolve_report(
    data: ReportResolveRequest, request: Request, user: OptionalUserDep, source: ReportSourceDep
) -> ReportResolved:
    code = parse_report_code(data.url)
    if code is None:
        message = CLASSIC_LINK_MESSAGE if is_classic_link(data.url) else INVALID_LINK_MESSAGE
        raise api_error(422, "invalid_link", message)
    # Colar o link, "Atualizar lutas" e a atualização automática (luta subindo) leem a lista
    # de novo: o log pode ser ao vivo. Menos de 8 s depois da última busca vem a lista
    # guardada. Se a busca falhar com o WCL fora do ar, ou o cliente passar do limite de
    # consultas, e houver lista guardada, ela vem com `stale`, `stale_message` e
    # `stale_code`; sem lista guardada, vem o erro. Logo depois de uma falha (8 s, ou o
    # `Retry-After` do limite), a resposta é essa mesma, sem chamar o WCL.
    return refresh_report(source, code, request_client(request, user))


@router.get("/{code}/fights/{fight_id}/players")
def fight_players(
    code: str, fight_id: int, request: Request, user: OptionalUserDep, source: ReportSourceDep
) -> FightPlayers:
    """Magos Arcanos da luta escolhida, com spec e item level dela. Só luta suportada."""
    client = request_client(request, user)
    report, fight = load_fight(source, code, fight_id, client)
    players = load_fight_players(source, report.code, fight.id, client)
    return FightPlayers(report_code=report.code, fight_id=fight.id, players=players)


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
    por janela, com um teto de `PREFETCH_GLOBAL_LIMIT` por hora no processo (429
    `prefetch_limit` nos dois). A tela ignora esses erros: a análise busca sozinha.
    """
    check_plan_limit(session, user)
    report, fight = load_fight(source, code, fight_id)
    player = load_player(source, report, fight, data.actor_id)
    client = request_client(request, user)
    try:
        status = load_report(
            _SourceCall(lambda: source.prefetch(report.code, fight.id, player.actor_id, client)),
            report.code,
        )
    except PrefetchLimitError:
        raise api_error(429, "prefetch_limit", PREFETCH_LIMIT_MESSAGE) from None
    return PrefetchStatus(status=status)
