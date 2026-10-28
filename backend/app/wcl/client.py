"""Cliente da API v2 do Warcraft Logs (GraphQL, fluxo client credentials)."""

import threading
import time
from typing import Any

import httpx

from app.config import get_settings

TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
API_URL = "https://www.warcraftlogs.com/api/v2/client"

# Renova o token um pouco antes de expirar, para não falhar no meio de uma busca.
TOKEN_MARGIN_S = 60
EVENTS_PAGE_LIMIT = 10000

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


UNAVAILABLE_MESSAGE = "O Warcraft Logs não respondeu agora. Tente de novo em alguns minutos."


class WclError(RuntimeError):
    """Erro devolvido pela API do Warcraft Logs."""


class WclUnavailableError(WclError):
    """A API não atendeu por motivo nosso ou dela, não do report.

    Limite de pontos (429), fora do ar (5xx), timeout/erro de rede, resposta que não é
    JSON ou credenciais do servidor ausentes/recusadas. `user_message` é o texto pronto
    para o usuário (item 8.2); a rota só repassa.
    """

    def __init__(self, detail: str, user_message: str = UNAVAILABLE_MESSAGE) -> None:
        super().__init__(detail)
        self.user_message = user_message


# Status em que a culpa é da API (ou do limite de pontos), não do report pedido.
UNAVAILABLE_STATUS = {429, 500, 502, 503, 504}


class WclClient:
    """Pode ser usado por várias threads ao mesmo tempo (rotas síncronas do FastAPI)."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 60,
    ) -> None:
        self._auth = (client_id, client_secret)
        self._http = httpx.Client(transport=transport, timeout=timeout_s)
        self._token: str | None = None
        self._token_expires_at = 0.0
        # Só uma thread renova o token; as outras esperam e usam o novo.
        self._token_lock = threading.Lock()

    @classmethod
    def from_env(cls, **kwargs: Any) -> "WclClient":
        # Mesmas configurações do resto do backend (variáveis de ambiente + backend/.env).
        settings = get_settings()
        client_id, client_secret = settings.wcl_client_id, settings.wcl_client_secret
        if not client_id or not client_secret:
            raise WclUnavailableError(
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
        except httpx.RequestError as exc:
            raise WclUnavailableError(f"Sem resposta do Warcraft Logs: {exc!r}") from exc

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            # Ex.: página de erro em HTML do proxy na frente da API.
            raise WclUnavailableError(f"Resposta não é JSON: {response.text[:200]}") from exc

    def _access_token(self) -> str:
        with self._token_lock:
            if self._token is None or time.monotonic() >= self._token_expires_at:
                response = self._post(
                    TOKEN_URL, data={"grant_type": "client_credentials"}, auth=self._auth
                )
                if response.status_code != 200:
                    # Credencial recusada ou API fora do ar: nos dois casos não é o report.
                    raise WclUnavailableError(
                        f"Falha ao obter token ({response.status_code}): {response.text[:500]}"
                    )
                body = self._json(response)
                self._token = body["access_token"]
                self._token_expires_at = time.monotonic() + body["expires_in"] - TOKEN_MARGIN_S
            return self._token

    def _drop_token(self, token: str) -> None:
        # Só descarta se ninguém renovou no meio tempo, para não jogar fora um token novo.
        with self._token_lock:
            if self._token == token:
                self._token = None

    def query(self, gql: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {"query": gql, "variables": variables or {}}
        for attempt in range(2):
            token = self._access_token()
            headers = {"Authorization": f"Bearer {token}"}
            response = self._post(API_URL, json=payload, headers=headers)
            if response.status_code == 401 and attempt == 0:
                # Token revogado ou expirado antes da hora: pede outro e tenta de novo.
                self._drop_token(token)
                continue
            break
        status = response.status_code
        if status in UNAVAILABLE_STATUS or status == 401:
            # 401 mesmo com token novo: credencial do servidor recusada.
            raise WclUnavailableError(f"Erro HTTP {status}: {response.text[:500]}")
        if status != 200:
            raise WclError(f"Erro HTTP {status}: {response.text[:500]}")
        body = self._json(response)
        if body.get("errors"):
            messages = "; ".join(e.get("message", str(e)) for e in body["errors"])
            raise WclError(f"Erro no GraphQL: {messages}")
        return body["data"]

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
            )
            page = data["reportData"]["report"]["events"]
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
