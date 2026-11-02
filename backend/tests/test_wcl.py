import gzip
import json
import threading
import time
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.wcl.anonymize import anonymize_fight
from app.wcl.client import (
    API_URL,
    TOKEN_URL,
    UNEXPECTED_MESSAGE,
    WclClient,
    WclUnavailableError,
    close_shared_client,
    shared_client,
    stop_shared_client,
)
from app.wcl.fetch import bracket_index, bracket_range

FIXTURES = Path(__file__).parent / "fixtures" / "nekzali_mythic_326_328"


def make_client(handler) -> WclClient:
    return WclClient("id", "secret", transport=httpx.MockTransport(handler))


def token_response(expires_in: int = 3600) -> httpx.Response:
    return httpx.Response(200, json={"access_token": "tok", "expires_in": expires_in})


def test_token_is_reused_between_queries():
    calls = {"token": 0, "api": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            calls["token"] += 1
            return token_response()
        calls["api"] += 1
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"data": {"ok": True}})

    client = make_client(handler)
    client.query("{ ok }")
    client.query("{ ok }")

    assert calls == {"token": 1, "api": 2}


def test_expired_token_is_renewed():
    calls = {"token": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            calls["token"] += 1
            return token_response(expires_in=0)  # já nasce vencido (margem de 60 s)
        return httpx.Response(200, json={"data": {}})

    client = make_client(handler)
    client.query("{ a }")
    client.query("{ a }")

    assert calls["token"] == 2


def test_401_requests_new_token_and_retries():
    responses = iter([httpx.Response(401), httpx.Response(200, json={"data": {"ok": 1}})])
    calls = {"token": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            calls["token"] += 1
            return token_response()
        return next(responses)

    assert make_client(handler).query("{ ok }") == {"ok": 1}
    assert calls["token"] == 2


def test_events_follow_pagination():
    pages = {
        0: {"data": [{"timestamp": 1}, {"timestamp": 2}], "nextPageTimestamp": 3},
        3: {"data": [{"timestamp": 3}], "nextPageTimestamp": None},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return token_response()
        assert str(request.url) == API_URL
        start = json.loads(request.content)["variables"]["startTime"]
        return httpx.Response(
            200, json={"data": {"reportData": {"report": {"events": pages[start]}}}}
        )

    events = make_client(handler).events("CODE", 1, 0, 10, "Casts", source_id=5)

    assert [e["timestamp"] for e in events] == [1, 2, 3]


def test_small_queries_wait_10_s_and_events_60_s():
    read_timeouts: dict[str, float] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return token_response()
        query = json.loads(request.content)["query"]
        kind = "events" if "events(" in query else "small"
        read_timeouts[kind] = request.extensions["timeout"]["read"]
        if kind == "events":
            page = {"data": [], "nextPageTimestamp": None}
            return httpx.Response(200, json={"data": {"reportData": {"report": {"events": page}}}})
        return httpx.Response(200, json={"data": {"ok": True}})

    client = make_client(handler)
    client.query("query { ok }")
    client.events("CODE", 1, 0, 10, "Casts")

    assert read_timeouts == {"small": 10, "events": 60}


def test_missing_credentials_message(monkeypatch):
    # Sem ler o backend/.env do desenvolvedor, que pode ter as chaves de verdade.
    empty = Settings(_env_file=None, wcl_client_id="", wcl_client_secret="")
    monkeypatch.setattr("app.wcl.client.get_settings", lambda: empty)

    # Problema do servidor, não do report: vira "WCL indisponível" na API.
    with pytest.raises(WclUnavailableError, match="WCL_CLIENT_ID"):
        WclClient.from_env()


def api_status(status: int, token_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            if token_status != 200:
                return httpx.Response(token_status, json={"error": "invalid_client"})
            return token_response()
        return httpx.Response(status, json={"error": "x"})

    return make_client(handler)


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_rate_limit_and_server_errors_are_unavailable(status):
    with pytest.raises(WclUnavailableError, match=str(status)):
        api_status(status).query("{ x }")


def test_other_http_errors_are_unexpected():
    # GraphQL responde 200 até para erro de sintaxe: outro status não é do report.
    with pytest.raises(WclUnavailableError) as info:
        api_status(400).query("{ x }")

    assert info.value.user_message == UNEXPECTED_MESSAGE


@pytest.mark.parametrize("token_status", [401, 503])
def test_token_failure_is_unavailable(token_status):
    with pytest.raises(WclUnavailableError, match="(?i)token"):
        api_status(200, token_status=token_status).query("{ x }")


def test_401_twice_is_unavailable():
    # Token novo também recusado: credencial do servidor, não o report.
    with pytest.raises(WclUnavailableError, match="401"):
        api_status(401).query("{ x }")


@pytest.mark.parametrize("error", [httpx.ConnectError("sem rede"), httpx.ReadTimeout("demorou")])
def test_network_errors_are_unavailable(error):
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(WclUnavailableError):
        make_client(handler).query("{ x }")


def test_non_json_response_is_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return token_response()
        return httpx.Response(200, text="<html>Bad gateway</html>")

    with pytest.raises(WclUnavailableError, match="JSON"):
        make_client(handler).query("{ x }")


def test_concurrent_queries_share_one_token():
    # Rotas síncronas rodam em threads: várias chegam juntas sem token e só uma o pede.
    calls = {"token": 0}
    threads_n = 8
    start = threading.Barrier(threads_n)

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            calls["token"] += 1
            time.sleep(0.05)  # dá tempo das outras threads chegarem
            return token_response()
        return httpx.Response(200, json={"data": {"ok": True}})

    client = make_client(handler)
    errors: list = []

    def run() -> None:
        start.wait()
        try:
            client.query("{ ok }")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(threads_n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert calls["token"] == 1


def test_401_keeps_token_renewed_by_another_thread():
    calls = {"token": 0}
    tokens = iter(["velho", "novo"])

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            calls["token"] += 1
            return httpx.Response(200, json={"access_token": next(tokens), "expires_in": 3600})
        return httpx.Response(200, json={"data": {}})

    client = make_client(handler)
    client.query("{ a }")  # token "velho"
    client._drop_token("velho")
    client.query("{ a }")  # renova: "novo"
    client._drop_token("velho")  # 401 atrasado de quem usou o velho

    client.query("{ a }")

    assert calls["token"] == 2  # o "novo" continuou valendo


@pytest.fixture
def wcl_credentials(monkeypatch):
    settings = Settings(_env_file=None, wcl_client_id="id", wcl_client_secret="secret")
    monkeypatch.setattr("app.wcl.client.get_settings", lambda: settings)
    close_shared_client()
    yield monkeypatch
    close_shared_client()


def test_shared_client_is_one_per_process(wcl_credentials):
    client = shared_client()

    assert shared_client() is client


def test_close_shared_client_creates_a_new_one(wcl_credentials):
    first = shared_client()
    close_shared_client()

    assert shared_client() is not first


def test_stop_ends_the_events_between_pages():
    # Desligamento do app: a busca de eventos para na próxima página, sem baixar o resto.
    client: WclClient
    pages: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return token_response()
        start = json.loads(request.content)["variables"]["startTime"]
        pages.append(start)
        client.stop()  # o desligamento chega enquanto a 1ª página baixa
        page = {"data": [{"timestamp": start}], "nextPageTimestamp": start + 1}
        return httpx.Response(200, json={"data": {"reportData": {"report": {"events": page}}}})

    client = make_client(handler)
    with pytest.raises(WclUnavailableError) as info:
        client.events("CODE", 1, 0, 10, "Casts")

    assert pages == [0]
    assert info.value.error_code == "wcl_unavailable"


def test_stop_shared_client_does_not_create_one(wcl_credentials):
    stop_shared_client()  # sem cliente ainda: nada a parar, nada criado
    client = shared_client()
    stop_shared_client()

    assert client._stopped.is_set()


def test_drop_token_does_not_wait_forever_for_the_lock():
    # Outra thread está renovando o token (lock preso): quem foi recusado não trava.
    client = WclClient("id", "secret", token_wait_s=0.05)
    client._token = "velho"
    client._token_lock.acquire()
    try:
        client._drop_token("velho")
    finally:
        client._token_lock.release()

    assert client._token == "velho"  # quem renova é a outra thread
    client.close()


def test_shared_client_retries_after_missing_credentials(wcl_credentials):
    empty = Settings(_env_file=None, wcl_client_id="", wcl_client_secret="")
    wcl_credentials.setattr("app.wcl.client.get_settings", lambda: empty)
    with pytest.raises(WclUnavailableError):
        shared_client()

    # Falha não fica guardada: com as chaves no lugar, o próximo uso cria o cliente.
    filled = Settings(_env_file=None, wcl_client_id="id", wcl_client_secret="secret")
    wcl_credentials.setattr("app.wcl.client.get_settings", lambda: filled)
    assert isinstance(shared_client(), WclClient)


def test_bracket_index_for_reference_item_level():
    # Nek'zali Mítico: brackets de 3 em 3 começando em 272.
    assert bracket_index(327, 272, 3) == 19
    assert bracket_range(19, 272, 3) == (326, 328)
    assert bracket_index(326, 272, 3) == bracket_index(328, 272, 3) == 19
    assert bracket_index(329, 272, 3) == 20


def sample_fight() -> dict:
    return {
        "meta": {"report": "SECRETCODE", "report_start_time": 1},
        "actors": [
            {"id": 7, "name": "Fulano", "server": "Azralon", "type": "Player", "gameID": 111},
            {"id": 3, "name": "Ciclano", "server": "Nemesis", "type": "Player", "gameID": 222},
            {"id": 9, "name": "Totó", "type": "Pet", "petOwner": 3, "gameID": 0},
            {"id": 1, "name": "Nek'zali", "type": "NPC", "gameID": 259927},
        ],
        "player": {
            "actor": {"id": 7, "name": "Fulano", "type": "Player"},
            "details": {"id": 7, "name": "Fulano", "server": "Azralon", "guid": 111},
        },
    }


def test_anonymize_hides_names_and_report():
    anon, mapping = anonymize_fight(sample_fight(), "top01")
    text = json.dumps(anon, ensure_ascii=False)

    for secret in ("Fulano", "Ciclano", "Azralon", "Nemesis", "Totó", "SECRETCODE", "111"):
        assert secret not in text
    assert anon["player"]["actor"]["display_name"] == "top01"
    assert anon["player"]["details"]["display_name"] == "top01"
    assert {a["display_name"] for a in anon["actors"] if a["type"] == "Player"} == {
        "top01",
        "raid_01",
    }
    # NPC continua com o nome (vem do jogo, não é dado pessoal).
    assert any(a.get("name") == "Nek'zali" for a in anon["actors"])
    # Mapa permite mostrar os nomes de volta.
    assert mapping["top01"]["name"] == "Fulano"
    assert mapping["top01"]["report"] == "SECRETCODE"
    assert mapping["raid_01"]["name"] == "Ciclano"


def test_anonymize_keeps_names_in_keep():
    anon, mapping = anonymize_fight(
        sample_fight(), "reference", keep=frozenset({"Fulano"}), hide_report=False
    )

    assert anon["player"]["actor"]["name"] == "Fulano"
    assert anon["player"]["details"]["name"] == "Fulano"
    assert anon["meta"]["report"] == "SECRETCODE"
    assert "Fulano" not in mapping


@pytest.mark.skipif(not FIXTURES.exists(), reason="rode scripts/save_fixtures.py")
@pytest.mark.parametrize(
    "file", ["reference_harmonist.json.gz"] + [f"top{i:02d}.json.gz" for i in range(1, 11)]
)
def test_fixture_has_what_the_engine_needs(file):
    fight = json.loads(gzip.decompress((FIXTURES / file).read_bytes()))
    events = fight["events"]

    assert fight["meta"]["fight"]["kill"] is True
    assert [p["id"] for p in fight["meta"]["fight"]["phaseTransitions"]] == [1, 2, 3]
    assert any(
        e["type"] == "applybuffstack" and e["abilityGameID"] == 1242974 for e in events["buffs"]
    )
    assert any(e["type"] == "cast" and e["abilityGameID"] == 365350 for e in events["casts"])
    assert 326 <= fight["player"]["details"]["maxItemLevel"] <= 328
    # Buffs externos (de outros jogadores) também vêm, e todos os buffs são no jogador.
    player_id = fight["player"]["actor"]["id"]
    assert all(e["targetID"] == player_id for e in events["buffs"])
    assert any(e["sourceID"] != player_id for e in events["buffs"])
