"""Leitura do link do Warcraft Logs, lista de lutas, Magos de cada luta e pré-busca dos
eventos da luta do jogador (RF03, RF04)."""

import ipaddress
import logging
from collections.abc import Callable, Hashable
from typing import Annotated

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
    MIN_FIGHT_S,
    QUERY_LIMIT_CODE,
    SAMPLE_REPORT_CODE,
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
from app.services.tops import OwnLog, TopsSource, get_tops_source
from app.wcl.client import UNAVAILABLE_MESSAGE, WCL_UNAVAILABLE_CODE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["análises"])

ReportSourceDep = Annotated[ReportSource, Depends(get_report_source)]
TopsSourceDep = Annotated[TopsSource, Depends(get_tops_source)]

# Status de cada código da fonte: do Warcraft Logs (tentar de novo depois resolve), nosso, ou
# o limite de consultas do cliente.
SOURCE_ERROR_STATUS = {WCL_UNAVAILABLE_CODE: 503, UNEXPECTED_ERROR_CODE: 500, QUERY_LIMIT_CODE: 429}
# Luta subindo ou com o envio parado: vale buscar a lista de novo antes de recusar.
UPLOAD_WAIT_CODES = ("in_progress", "upload_paused")

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


def call_source[T](source: ReportSource, call: Callable[[], T]) -> T:
    """Chama a fonte traduzindo os erros dela para a resposta: o único lugar que faz isso
    (mesmos códigos e mensagens em todas as rotas)."""
    try:
        return call()
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


def load_report(source: ReportSource, code: str, client: Hashable | None = None) -> ReportResolved:
    """A lista de lutas (a guardada, se houver)."""
    return call_source(source, lambda: source.get_report(code, client=client))


def refresh_report(
    source: ReportSource, code: str, client: Hashable | None = None
) -> ReportResolved:
    # O exemplo ignora `refresh` (não tem lutas novas).
    return call_source(source, lambda: source.get_report(code, refresh=True, client=client))


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
    if fight.unsupported_code in UPLOAD_WAIT_CODES and not refreshed:
        # A lista guardada pode ser de quando a luta ainda subia (ou o envio estava parado):
        # busca uma vez antes de recusar. A trava de 8 s e a pausa depois de falha evitam gasto.
        report = refresh_report(source, code, client)
        fight = _find(report, fight_id) or fight
    # Luta subindo: a duração ainda vai crescer, então o motivo é ela estar em andamento.
    if fight.unsupported_code in UPLOAD_WAIT_CODES:
        raise api_error(422, "unsupported_fight", fight.unsupported_reason)
    # Curta só se esse é o motivo: luta de outro chefe ainda subindo tem duração parcial.
    if fight.duration_s < MIN_FIGHT_S and fight.unsupported_code in (None, "short"):
        raise api_error(
            422, "fight_too_short", "A luta tem menos de 60 s. Escolha uma tentativa mais longa."
        )
    if not fight.supported:
        raise api_error(422, "unsupported_fight", fight.unsupported_reason)
    return report, fight


def load_fight_players(
    source: ReportSource, code: str, fight_id: int, client: Hashable | None = None
) -> list[PlayerOption]:
    return call_source(source, lambda: source.get_fight_players(code, fight_id, client=client))


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
    tops: TopsSourceDep,
) -> PrefetchStatus:
    """Põe na fila os eventos da luta do jogador (~18 pontos) assim que ele fica definido na
    tela, para a análise não esperar por eles. Responde na hora, sem esperar a busca.

    Pede também, numa fila própria, os tops do bracket do jogador (item 12.13: ~135 pontos
    quando o bracket não está no cache, com teto por hora no processo). Falha dessa parte
    só vai para o log: a análise busca os tops sozinha.

    Login opcional. Conta sem análises no mês não pré-busca (403 `plan_limit`); cada cliente
    tem uma pré-busca na fila (a nova tira a anterior) e no máximo `PREFETCH_LIMIT` novas
    por janela, com um teto de `PREFETCH_GLOBAL_LIMIT` por hora no processo (429
    `prefetch_limit` nos dois). A tela ignora esses erros: a análise busca sozinha.
    """
    check_plan_limit(session, user)
    client = request_client(request, user)
    # Lista e Magos da luta contam no limite de consultas como nas outras rotas (cache não).
    report, fight = load_fight(source, code, fight_id, client)
    player = load_player(source, report, fight, data.actor_id, client)
    try:
        status = call_source(
            source, lambda: source.prefetch(report.code, fight.id, player.actor_id, client)
        )
    except PrefetchLimitError:
        raise api_error(429, "prefetch_limit", PREFETCH_LIMIT_MESSAGE) from None
    prefetch_tops(tops, report, fight, player)
    return PrefetchStatus(status=status)


def prefetch_tops(
    tops: TopsSource, report: ReportResolved, fight: FightOption, player: PlayerOption
) -> None:
    """Tops do bracket do jogador em segundo plano. Lista guardada antes dos ids do encontro
    ou jogador sem item level: não há como achar o bracket, e a análise busca depois."""
    if fight.encounter_id is None or fight.difficulty_id is None or player.item_level is None:
        return
    try:
        tops.prefetch_tops(
            fight.encounter_id,
            fight.difficulty_id,
            player.item_level,
            OwnLog(report.code, fight.id, player.name),
        )
    except Exception:
        logger.exception("Pré-busca dos tops de %s/%s não entrou na fila", report.code, fight.id)
