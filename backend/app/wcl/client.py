"""Cliente da API v2 do Warcraft Logs (GraphQL, fluxo client credentials).

Também decide de quem é cada erro (item 12.8): report privado ou inexistente vira `WclError`
(a fonte mostra "confira se está público"); o resto vira `WclUnavailableError` com a
mensagem pronta para o usuário, dizendo se o problema é do Warcraft Logs (fora do ar,
limite de pedidos, Cloudflare, lentidão) ou nosso (configuração).
"""

import logging
import math
import threading
import time
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.config import get_settings
from app.errors import UNEXPECTED_ERROR_CODE

logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
API_URL = "https://www.warcraftlogs.com/api/v2/client"

# Renova o token um pouco antes de expirar, para não falhar no meio de uma busca.
TOKEN_MARGIN_S = 60
EVENTS_PAGE_LIMIT = 10000

# Tempos de espera. Consultas pequenas (lista de lutas, Magos, metadados) voltam em menos
# de 1 s: passou de 10 s, o WCL travou e o usuário já está esperando demais sem retorno
# (limite de atenção de Nielsen). Só as páginas de 10 mil eventos, que rodam em segundo
# plano na pré-busca, podem levar dezenas de segundos. O token também é pequeno.
API_TIMEOUT = httpx.Timeout(connect=5, read=10, write=10, pool=5)
EVENTS_TIMEOUT = httpx.Timeout(connect=5, read=60, write=10, pool=5)
TOKEN_TIMEOUT = httpx.Timeout(connect=5, read=10, write=5, pool=5)
# Quanto uma consulta espera na fila enquanto outra thread pede o token. Sem limite, com o
# endpoint do token travado, N pedidos juntos esperariam N × o tempo do token.
TOKEN_WAIT_S = 10

EVENTS_QUERY = """
query Events(
  $code: String!, $fightID: Int!, $startTime: Float!, $endTime: Float!,
  $dataType: EventDataType!, $hostilityType: HostilityType!,
  $sourceID: Int, $targetID: Int, $abilityID: Float, $limit: Int!
) {
  reportData {
    report(code: $code) {
      events(
        fightIDs: [$fightID], startTime: $startTime, endTime: $endTime,
        dataType: $dataType, hostilityType: $hostilityType,
        sourceID: $sourceID, targetID: $targetID, abilityID: $abilityID, limit: $limit
      ) { data nextPageTimestamp }
    }
  }
}
"""


# Códigos da API (item 12.3) para cada causa. Do Warcraft Logs (fora do ar, limite, lentidão):
# 503, vale tentar de novo daqui a pouco. Nossos (consulta com defeito, credenciais do
# servidor): 500, tentar de novo não resolve até alguém corrigir o LogCoach.
WCL_UNAVAILABLE_CODE = "wcl_unavailable"

# --- Mensagens ao usuário (item 8.2) ------------------------------------------
# Dizem o que houve, de quem é o problema e o que fazer (heurística 9 de Nielsen).

UNAVAILABLE_MESSAGE = (
    "O Warcraft Logs está fora do ar ou instável agora. O problema é do lado deles, "
    "não do seu relatório. Tente de novo em alguns minutos."
)
TIMEOUT_MESSAGE = (
    "O Warcraft Logs demorou demais para responder (lentidão do lado deles). "
    "Tente de novo em alguns minutos."
)
NETWORK_MESSAGE = (
    "O LogCoach não conseguiu se conectar ao Warcraft Logs. Pode ser instabilidade do "
    "lado deles ou da nossa conexão. Tente de novo em alguns minutos."
)
BLOCKED_MESSAGE = (
    "A proteção do site do Warcraft Logs (Cloudflare) barrou o acesso do LogCoach por "
    "enquanto. Não é o seu relatório. Tente de novo em alguns minutos."
)
CONFIG_MESSAGE = (
    "Erro de configuração do LogCoach: nosso acesso ao Warcraft Logs não está funcionando. "
    "O problema é nosso, não do seu relatório nem do Warcraft Logs. Tente de novo mais tarde."
)
QUERY_MESSAGE = (
    "Erro inesperado no LogCoach: a consulta que fazemos ao Warcraft Logs está com defeito. "
    "O problema é nosso, não do seu relatório nem do Warcraft Logs. Tente de novo mais tarde."
)
UNEXPECTED_MESSAGE = (
    "O Warcraft Logs respondeu com um erro inesperado. Tente de novo; se continuar, "
    "recarregue a página."
)
RATE_LIMIT_PREFIX = (
    "O Warcraft Logs está limitando os pedidos do LogCoach agora (limite de uso da API "
    "deles). Seu relatório não tem problema: "
)


def rate_limit_message(wait_s: float | None = None) -> str:
    """Limite de pedidos: com o tempo do `Retry-After`, diz quando tentar."""
    if wait_s is None:
        # O limite de pontos do WCL é por hora; sem o cabeçalho, não dá para saber quanto falta.
        return RATE_LIMIT_PREFIX + (
            "tente de novo em alguns minutos. Se continuar, o limite libera em até 1 hora."
        )
    minutes = max(1, math.ceil(wait_s / 60))
    when = "1 minuto" if minutes == 1 else f"{minutes} minutos"
    return RATE_LIMIT_PREFIX + f"tente de novo daqui a uns {when}."


class WclError(RuntimeError):
    """Erro devolvido pela API do Warcraft Logs."""


class WclUnavailableError(WclError):
    """A API não atendeu por motivo nosso ou dela, não do report.

    Limite de pedidos (429), fora do ar (5xx, Cloudflare, manutenção, erro interno do
    GraphQL), timeout/erro de rede, resposta inválida ou credenciais do servidor
    ausentes/recusadas. `user_message` é o texto pronto para o usuário (item 8.2) e
    `error_code` o código da API, escolhidos aqui pela causa; a rota só repassa.
    """

    def __init__(
        self,
        detail: str,
        user_message: str = UNAVAILABLE_MESSAGE,
        error_code: str = WCL_UNAVAILABLE_CODE,
    ) -> None:
        super().__init__(detail)
        self.user_message = user_message
        self.error_code = error_code


# --- Classificação das respostas ------------------------------------------------

# Erros de GraphQL (HTTP 200) que são do report pedido, como o WCL escreve.
REPORT_ERRORS = ("this report does not exist", "you do not have permission to view this report")
# Erros de GraphQL que são instabilidade do WCL (Lighthouse/Laravel sem detalhes).
OUTAGE_ERRORS = ("internal server error", "server error", "service unavailable", "maintenance")
RATE_LIMIT_ERRORS = ("rate limit", "too many requests")
# Validação do GraphQL: a consulta que montamos está errada (campo, argumento ou variável).
QUERY_ERRORS = (
    "syntax error",
    "cannot query field",
    "unknown argument",
    "unknown type",
    'variable "$',
    "must be of type",
    "expected type",
)
REPORT_PATH = ["reportData", "report"]

BODY_LOG_CHARS = 1000


def _snippet(response: httpx.Response, chars: int = 500) -> str:
    return " ".join(response.text[:chars].split())


def _is_html(response: httpx.Response) -> bool:
    content_type = response.headers.get("content-type", "")
    return "text/html" in content_type or response.text.lstrip().startswith("<")


def _retry_after_s(response: httpx.Response) -> float | None:
    """Segundos do `Retry-After` (número ou data HTTP); None se não veio ou não dá para ler."""
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError):
        return None


def _http_error(response: httpx.Response, what: str) -> WclError:
    """Status diferente de 200 que não é de token recusado (esse a chamada trata antes)."""
    status = response.status_code
    detail = f"{what}: HTTP {status}: {_snippet(response)}"
    if status == 429:
        # Limite de pontos da API e também o 1015 do Cloudflare (excesso de pedidos por IP).
        return WclUnavailableError(detail, rate_limit_message(_retry_after_s(response)))
    if status >= 500:
        # 500–504, 52x do Cloudflare (origem fora do ar ou sem resposta) e manutenção.
        return WclUnavailableError(detail, UNAVAILABLE_MESSAGE)
    if status == 403 and ("cf-mitigated" in response.headers or _is_html(response)):
        # Página de desafio/bloqueio do Cloudflare na frente da API.
        return WclUnavailableError(detail, BLOCKED_MESSAGE)
    logger.error("Resposta inesperada do Warcraft Logs (%s): %s", what, _snippet(response, 2000))
    return WclUnavailableError(detail, UNEXPECTED_MESSAGE)


def _config_error(detail: str) -> WclUnavailableError:
    # Problema nosso: vai para o log como erro, e o usuário só sabe que é configuração.
    logger.error("Configuração do Warcraft Logs: %s", detail)
    return WclUnavailableError(detail, CONFIG_MESSAGE, UNEXPECTED_ERROR_CODE)


def _report_is_null(data: Any) -> bool:
    """`data.reportData.report` veio explicitamente nulo (o WCL faz isso com report fora)."""
    report_data = data.get("reportData") if isinstance(data, dict) else None
    return isinstance(report_data, dict) and "report" in report_data and not report_data["report"]


def _graphql_error(errors: list[Any], data: Any = None) -> WclError:
    """Erros de GraphQL chegam com HTTP 200. Só o que for do report vira `WclError` puro."""
    entries = [e if isinstance(e, dict) else {"message": str(e)} for e in errors]
    messages = [str(e.get("message", e)) for e in entries]
    detail = "Erro no GraphQL: " + "; ".join(messages)
    lowered = [m.lower() for m in messages]

    def mentions(words: tuple[str, ...]) -> bool:
        return any(word in message for message in lowered for word in words)

    if mentions(RATE_LIMIT_ERRORS):
        return WclUnavailableError(detail, rate_limit_message())
    if mentions(OUTAGE_ERRORS):
        return WclUnavailableError(detail, UNAVAILABLE_MESSAGE)
    if mentions(QUERY_ERRORS):
        # Bug nosso (consulta desatualizada com o schema do WCL): tentar de novo não resolve.
        logger.error("Consulta ao Warcraft Logs com defeito: %s", detail[:BODY_LOG_CHARS])
        return WclUnavailableError(detail, QUERY_MESSAGE, UNEXPECTED_ERROR_CODE)
    on_report = all(e.get("path") == REPORT_PATH for e in entries)
    if mentions(REPORT_ERRORS) or on_report or _report_is_null(data):
        # Privado ou inexistente: o WCL devolve `report: null` junto, no campo do report.
        return WclError(detail)
    logger.error("Erro de GraphQL não reconhecido do Warcraft Logs: %s", detail[:BODY_LOG_CHARS])
    return WclUnavailableError(detail, UNEXPECTED_MESSAGE)


def _token_refused(response: httpx.Response) -> bool:
    """Token recusado na API. O WCL responde 404 em HTML (observado), não 401."""
    return response.status_code == 401 or (response.status_code == 404 and _is_html(response))


class WclClient:
    """Pode ser usado por várias threads ao mesmo tempo (rotas síncronas do FastAPI)."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        transport: httpx.BaseTransport | None = None,
        timeout: httpx.Timeout = API_TIMEOUT,
        events_timeout: httpx.Timeout = EVENTS_TIMEOUT,
        token_timeout: httpx.Timeout = TOKEN_TIMEOUT,
        token_wait_s: float = TOKEN_WAIT_S,
    ) -> None:
        self._auth = (client_id, client_secret)
        self._http = httpx.Client(transport=transport, timeout=timeout)
        self._events_timeout = events_timeout
        self._token_timeout = token_timeout
        self._token_wait_s = token_wait_s
        self._token: str | None = None
        self._token_expires_at = 0.0
        # Só uma thread renova o token; as outras esperam (até `token_wait_s`) e usam o novo.
        self._token_lock = threading.Lock()

    @classmethod
    def from_env(cls, **kwargs: Any) -> "WclClient":
        # Mesmas configurações do resto do backend (variáveis de ambiente + backend/.env).
        settings = get_settings()
        client_id, client_secret = settings.wcl_client_id, settings.wcl_client_secret
        if not client_id or not client_secret:
            raise _config_error(
                "WCL_CLIENT_ID e WCL_CLIENT_SECRET não definidos. "
                "Copie backend/.env.example para backend/.env e preencha."
            )
        return cls(client_id, client_secret, **kwargs)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "WclClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _post(self, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._http.post(url, **kwargs)
        except httpx.TimeoutException as exc:
            raise WclUnavailableError(
                f"Warcraft Logs não respondeu a tempo: {exc!r}", TIMEOUT_MESSAGE
            ) from exc
        except httpx.RequestError as exc:
            raise WclUnavailableError(
                f"Sem conexão com o Warcraft Logs: {exc!r}", NETWORK_MESSAGE
            ) from exc

    @staticmethod
    def _json(response: httpx.Response, what: str) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            # Ex.: página de manutenção ou de erro em HTML na frente da API.
            raise WclUnavailableError(
                f"{what}: resposta não é JSON: {_snippet(response, 200)}", UNAVAILABLE_MESSAGE
            ) from exc
        if not isinstance(body, dict):
            logger.error("JSON inesperado do Warcraft Logs (%s): %s", what, _snippet(response))
            raise WclUnavailableError(f"{what}: JSON não é objeto", UNEXPECTED_MESSAGE)
        return body

    def _access_token(self) -> str:
        if not self._token_lock.acquire(timeout=self._token_wait_s):
            raise WclUnavailableError(
                f"Fila do token do Warcraft Logs passou de {self._token_wait_s} s", TIMEOUT_MESSAGE
            )
        try:
            if self._token is None or time.monotonic() >= self._token_expires_at:
                self._token, expires_in = self._request_token()
                self._token_expires_at = time.monotonic() + expires_in - TOKEN_MARGIN_S
            return self._token
        finally:
            self._token_lock.release()

    def _request_token(self) -> tuple[str, float]:
        response = self._post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=self._auth,
            timeout=self._token_timeout,
        )
        status = response.status_code
        if status in (400, 401) or (status == 403 and not _is_html(response)):
            # {"error": "invalid_client", ...}: a chave do .env está errada ou foi revogada.
            raise _config_error(f"Token recusado (HTTP {status}): {_snippet(response)}")
        if status != 200:
            raise _http_error(response, "Falha ao obter token")
        body = self._json(response, "Token")
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            logger.error("Resposta do token sem access_token (chaves: %s)", sorted(body))
            raise WclUnavailableError("Resposta do token sem access_token", UNEXPECTED_MESSAGE)
        expires_in = body.get("expires_in")
        if not isinstance(expires_in, int | float):
            expires_in = 3600  # o WCL manda ~360 dias; sem o campo, renova em 1 h
        return token, float(expires_in)

    def _drop_token(self, token: str) -> None:
        # Só descarta se ninguém renovou no meio tempo, para não jogar fora um token novo.
        with self._token_lock:
            if self._token == token:
                self._token = None

    def query(
        self,
        gql: str,
        variables: dict[str, Any] | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> dict[str, Any]:
        """`timeout` troca o tempo padrão (consulta pequena) só nesta chamada."""
        payload = {"query": gql, "variables": variables or {}}
        extra = {} if timeout is None else {"timeout": timeout}
        for attempt in range(2):
            token = self._access_token()
            headers = {"Authorization": f"Bearer {token}"}
            response = self._post(API_URL, json=payload, headers=headers, **extra)
            if _token_refused(response) and attempt == 0:
                # Token revogado ou expirado antes da hora: pede outro e tenta de novo.
                self._drop_token(token)
                continue
            break
        if _token_refused(response):
            # Recusado mesmo com token novo: credencial do servidor, não o report.
            raise _config_error(
                f"Token recusado na API (HTTP {response.status_code}): {_snippet(response, 200)}"
            )
        if response.status_code == 403 and not _is_html(response):
            raise _config_error(f"Acesso negado na API (HTTP 403): {_snippet(response)}")
        if response.status_code != 200:
            raise _http_error(response, "Consulta")
        body = self._json(response, "Consulta")
        if body.get("errors"):
            errors = body["errors"]
            raise _graphql_error(errors if isinstance(errors, list) else [errors], body.get("data"))
        data = body.get("data")
        if not isinstance(data, dict):
            logger.error("Resposta sem data do Warcraft Logs: %s", _snippet(response))
            raise WclUnavailableError("Resposta sem data", UNEXPECTED_MESSAGE)
        return data

    def events(
        self,
        code: str,
        fight_id: int,
        start_time: float,
        end_time: float,
        data_type: str,
        hostility_type: str = "Friendlies",
        source_id: int | None = None,
        target_id: int | None = None,
        ability_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Busca todos os eventos da janela, seguindo a paginação (nextPageTimestamp)."""
        events: list[dict[str, Any]] = []
        cursor = start_time
        while cursor is not None:
            data = self.query(
                EVENTS_QUERY,
                {
                    "code": code,
                    "fightID": fight_id,
                    "startTime": cursor,
                    "endTime": end_time,
                    "dataType": data_type,
                    "hostilityType": hostility_type,
                    "sourceID": source_id,
                    "targetID": target_id,
                    "abilityID": ability_id,
                    "limit": EVENTS_PAGE_LIMIT,
                },
                timeout=self._events_timeout,
            )
            report = (data.get("reportData") or {}).get("report")
            if report is None:
                raise WclError(f"Report {code} não encontrado.")
            page = report["events"]
            events.extend(page["data"])
            cursor = page["nextPageTimestamp"]
        return events


# --- Cliente do processo ------------------------------------------------------

_shared: WclClient | None = None
_shared_lock = threading.Lock()


def shared_client() -> WclClient:
    """O WclClient do backend: um por processo, criado no primeiro uso.

    Um token só para todas as rotas (renovado sozinho). Se faltarem as credenciais, levanta
    `WclUnavailableError` e tenta de novo na próxima chamada. Scripts usam o próprio cliente.
    """
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = WclClient.from_env()
        return _shared


def close_shared_client() -> None:
    """Fecha e esquece o cliente do processo (desligamento do app e isolamento dos testes)."""
    global _shared
    with _shared_lock:
        if _shared is not None:
            _shared.close()
        _shared = None
