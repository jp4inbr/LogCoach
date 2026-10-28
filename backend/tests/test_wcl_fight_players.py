"""FIGHT_PLAYERS contra a resposta real do Warcraft Logs (report de referência, luta 34).

A fixture é a resposta de uma consulta real de 28/10/2026, com os outros Magos trocados
por pseudônimos e sem reino (ver `_nota` no arquivo). Nada aqui acessa a internet.
"""

import json
from pathlib import Path

import httpx

from app.services.sources import ARCANE_LABEL, build_players
from app.wcl.client import TOKEN_URL, WclClient
from app.wcl.fetch import fetch_fight_players

FIXTURE = Path(__file__).parent / "fixtures" / "fight_players_XhrmBaYkGCAQjH2D_34.json"
HARMONIST = 455


def real_response() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def fixture_client(calls: list[str]) -> WclClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        calls.append(json.loads(request.content)["query"].split("(")[0].split()[-1])
        return httpx.Response(200, json=real_response())

    return WclClient("id", "secret", transport=httpx.MockTransport(handler))


def test_real_lists_have_the_same_order_and_types():
    fight = real_response()["data"]["reportData"]["report"]["fights"][0]
    ids, specs = fight["friendlyPlayers"], fight["friendlySpecs"]
    item_levels = fight["friendlyItemLevels"]

    assert len(ids) == len(specs) == len(item_levels) == 20
    assert all(isinstance(s, str) for s in specs)
    assert all(isinstance(i, int) for i in item_levels)
    # Mesma posição nas três listas: o Harmonist é Arcano com 327 nessa luta.
    position = ids.index(HARMONIST)
    assert (specs[position], item_levels[position]) == ("Arcane", 327)


def test_real_fixture_has_no_real_names_or_realms():
    actors = real_response()["data"]["reportData"]["report"]["masterData"]["actors"]

    assert all("server" not in a for a in actors)
    assert {a["name"] for a in actors if a["id"] != HARMONIST} <= {
        f"raid_{n:02d}" for n in range(1, len(actors))
    }


def test_arcane_mages_of_the_reference_fight():
    calls: list[str] = []

    raw = fetch_fight_players(fixture_client(calls), "XhrmBaYkGCAQjH2D", 34)
    players = build_players(raw)

    # Os dois Arcanos da luta; os outros Magos do report não jogaram essa luta.
    assert [(p["actor_id"], p["name"], p["spec"], p["item_level"]) for p in players] == [
        (HARMONIST, "Harmonist", ARCANE_LABEL, 327),
        (291, "raid_06", ARCANE_LABEL, 327),
    ]
    # Todas as specs vieram: nada de playerDetails (1 ponto a mais).
    assert calls == ["FightPlayers"]
