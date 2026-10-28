import gzip
import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.wcl.anonymize import anonymize_fight
from app.wcl.client import API_URL, TOKEN_URL, WclClient, WclError
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


def test_graphql_errors_raise_wcl_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return token_response()
        return httpx.Response(200, json={"errors": [{"message": "Invalid report"}]})

    with pytest.raises(WclError, match="Invalid report"):
        make_client(handler).query("{ x }")


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


def test_missing_credentials_message(monkeypatch):
    # Sem ler o backend/.env do desenvolvedor, que pode ter as chaves de verdade.
    empty = Settings(_env_file=None, wcl_client_id="", wcl_client_secret="")
    monkeypatch.setattr("app.wcl.client.get_settings", lambda: empty)

    with pytest.raises(WclError, match="WCL_CLIENT_ID"):
        WclClient.from_env()


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
