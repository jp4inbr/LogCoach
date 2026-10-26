"""Cliente da API v2 do Warcraft Logs (GraphQL, fluxo client credentials)."""

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


class WclError(RuntimeError):
    """Erro devolvido pela API do Warcraft Logs."""


class WclClient:
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

    @classmethod
    def from_env(cls, **kwargs: Any) -> "WclClient":
        # Mesmas configurações do resto do backend (variáveis de ambiente + backend/.env).
        settings = get_settings()
        client_id, client_secret = settings.wcl_client_id, settings.wcl_client_secret
        if not client_id or not client_secret:
            raise WclError(
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

    def _access_token(self) -> str:
        if self._token is None or time.monotonic() >= self._token_expires_at:
            response = self._http.post(
                TOKEN_URL, data={"grant_type": "client_credentials"}, auth=self._auth
            )
            if response.status_code != 200:
                raise WclError(f"Falha ao obter token ({response.status_code}): {response.text}")
            body = response.json()
            self._token = body["access_token"]
            self._token_expires_at = time.monotonic() + body["expires_in"] - TOKEN_MARGIN_S
        return self._token

    def query(self, gql: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {"query": gql, "variables": variables or {}}
        for attempt in range(2):
            headers = {"Authorization": f"Bearer {self._access_token()}"}
            response = self._http.post(API_URL, json=payload, headers=headers)
            if response.status_code == 401 and attempt == 0:
                # Token revogado ou expirado antes da hora: pede outro e tenta de novo.
                self._token = None
                continue
            break
        if response.status_code != 200:
            raise WclError(f"Erro HTTP {response.status_code}: {response.text[:500]}")
        body = response.json()
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
