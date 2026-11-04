"""Busca dos top N no Warcraft Logs (`wcl/tops.py`), com rankings e lutas falsos."""

import httpx
import pytest

from app.wcl import tops as wcl_tops
from app.wcl.client import WclError, WclUnavailableError
from app.wcl.fetch import FightNotFoundError
from app.wcl.players import PlayerNotFoundError


def ranking(i: int) -> dict:
    return {
        "name": f"Mago{i}",
        "server": {"name": "Area 52"},
        "amount": 300_000 - i,
        "duration": 400_000,
        "bracketData": 327,
        "report": {"code": f"R{i}", "fightID": i},
    }


@pytest.fixture
def fake_wcl(monkeypatch):
    """Ranking com 13 entradas; `broken` diz quais lutas falham e com que erro."""
    calls: dict = {"rankings": [], "fights": [], "broken": {}}

    def fetch_rankings(client, encounter_id, class_name, spec_name, difficulty, bracket, n):
        calls["rankings"].append({"bracket": bracket, "n": n})
        return [ranking(i) for i in range(1, 14)][:n]

    def fetch_fight(client, code, fight_id, *, name, server):
        calls["fights"].append((code, name, server))
        if code in calls["broken"]:
            raise calls["broken"][code]
        return {"meta": {"report": code}, "player": {"actor": {"name": name}}}

    monkeypatch.setattr(wcl_tops, "fetch_rankings", fetch_rankings)
    monkeypatch.setattr(wcl_tops, "fetch_fight", fetch_fight)
    return calls


def run(**kwargs):
    return wcl_tops.fetch_tops(None, 3470, "Mage", "Arcane", 5, 19, **kwargs)


def test_takes_the_first_n_by_name_and_server(fake_wcl):
    result = run()
    assert [t["ranking"]["name"] for t in result["tops"]] == [f"Mago{i}" for i in range(1, 11)]
    assert fake_wcl["rankings"] == [{"bracket": 19, "n": 13}]
    assert fake_wcl["fights"][0] == ("R1", "Mago1", "Area 52")
    assert len(fake_wcl["fights"]) == 10  # não abre as reservas sem precisar
    assert result["skipped"] == []


def test_skips_fights_that_do_not_open_and_fills_with_spares(fake_wcl):
    fake_wcl["broken"] = {
        "R2": PlayerNotFoundError("renomeado"),
        "R5": FightNotFoundError("sem luta"),
        "R7": WclError("privado"),
    }
    result = run()
    names = [t["ranking"]["name"] for t in result["tops"]]
    assert len(names) == 10
    assert "Mago2" not in names and names[-1] == "Mago13"
    assert [s["report"] for s in result["skipped"]] == ["R2", "R5", "R7"]
    # Cada top leva a posição real no ranking, não a ordem das lutas que abriram.
    assert [t["rank"] for t in result["tops"]][:3] == [1, 3, 4]
    # Todas as posições lidas continuam listadas, mesmo as que não abriram (RF21).
    assert [(r["rank"], r["report"], r["name"]) for r in result["rankings"][:2]] == [
        (1, "R1", "Mago1"),
        (2, "R2", "Mago2"),
    ]
    assert len(result["rankings"]) == 13 and result["rankings"][0]["server"] == "Area 52"


def test_wcl_down_stops_everything(fake_wcl):
    fake_wcl["broken"] = {"R3": WclUnavailableError("fora do ar")}
    with pytest.raises(WclUnavailableError):
        run()
    fake_wcl["broken"] = {"R3": httpx.ConnectError("rede")}
    with pytest.raises(httpx.ConnectError):
        run()


def test_short_ranking_returns_what_there_is(fake_wcl):
    result = run(n=3, spare=0)
    assert len(result["tops"]) == 3
    assert [r["rank"] for r in result["rankings"]] == [1, 2, 3]
