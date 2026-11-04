"""Achar o jogador nos atores do WCL: pelo id (analisado) ou por nome + reino (top 10)."""

import gzip
import json
from pathlib import Path

import pytest

from app.wcl.client import WclError
from app.wcl.players import PlayerNotFoundError, find_player, normalize_server


def actor(actor_id: int, name: str, server: str | None, kind: str = "Player") -> dict:
    return {"id": actor_id, "name": name, "server": server, "type": kind}


ACTORS = [
    actor(10, "Harmonist", "Azralon"),
    actor(11, "Sombra", "Area 52"),
    actor(12, "Sombra", "Tichondrius"),
    # Pet e NPC também vêm no masterData; não são jogadores.
    actor(13, "Sombra", "Area 52", kind="Pet"),
    actor(14, "Nek'zali", None, kind="NPC"),
]


def test_by_actor_id():
    assert find_player(ACTORS, actor_id=12) is ACTORS[2]


@pytest.mark.parametrize("actor_id", [14, 999])
def test_actor_id_that_is_not_a_player_in_the_report(actor_id):
    with pytest.raises(PlayerNotFoundError):
        find_player(ACTORS, actor_id=actor_id)


def test_unique_name_is_found_with_or_without_server():
    assert find_player(ACTORS, name="Harmonist") is ACTORS[0]
    assert find_player(ACTORS, name="Harmonist", server="azralon") is ACTORS[0]


def test_unique_name_on_another_server_is_not_found():
    with pytest.raises(PlayerNotFoundError):
        find_player(ACTORS, name="Harmonist", server="Tichondrius")


def test_unique_name_without_known_server_accepts_any_server():
    # Fixture anonimizada não tem reino: vale só o nome.
    actors = [actor(1, "Harmonist", None)]
    assert find_player(actors, name="Harmonist", server="Azralon")["id"] == 1


def test_unknown_name():
    with pytest.raises(PlayerNotFoundError):
        find_player(ACTORS, name="Ninguem")


def test_repeated_name_without_server_is_ambiguous():
    with pytest.raises(PlayerNotFoundError, match="mais de um"):
        find_player(ACTORS, name="Sombra")


def test_repeated_name_with_unknown_server_is_not_found():
    with pytest.raises(PlayerNotFoundError):
        find_player(ACTORS, name="Sombra", server="Azralon")


@pytest.mark.parametrize("server", ["Area 52", "area-52", "AREA52", "Area-52"])
def test_repeated_name_is_resolved_by_server(server):
    # O pet de mesmo nome e reino não conta.
    assert find_player(ACTORS, name="Sombra", server=server) is ACTORS[1]


def test_not_found_is_a_wcl_error():
    # Quem já trata WclError (ex.: save_fixtures) não precisa de outro except.
    assert issubclass(PlayerNotFoundError, WclError)


@pytest.mark.parametrize("kwargs", [{}, {"actor_id": 10, "name": "Harmonist"}])
def test_needs_exactly_one_key(kwargs):
    with pytest.raises(ValueError):
        find_player(ACTORS, **kwargs)


def test_reference_harmonist_is_actor_455():
    # Mesmo id do exemplo (app/samples) e do save_fixtures.py.
    path = Path(__file__).parent / "fixtures/nekzali_mythic_326_328/reference_harmonist.json.gz"
    fight = json.loads(gzip.decompress(path.read_bytes()))
    assert find_player(fight["actors"], actor_id=455)["name"] == "Harmonist"


def test_normalize_server():
    assert normalize_server("Area 52") == normalize_server("area-52") == "area52"
    assert normalize_server(None) == ""


class _FakeFightClient:
    """Responde ao FIGHT_META e guarda os filtros de cada busca de eventos."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def query(self, query, variables, timeout=None):
        return {
            "reportData": {
                "report": {
                    "startTime": 0,
                    "fights": [{"id": 1, "encounterID": 3470, "startTime": 0, "endTime": 1000}],
                    "masterData": {
                        "actors": [{**actor(10, "Harmonist", "Azralon"), "petOwner": None}],
                        "abilities": [],
                    },
                    "phases": [],
                    "playerDetails": {"data": {"playerDetails": {}}},
                }
            }
        }

    def events(self, code, fight_id, start, end, data_type, **filters):
        self.calls.append((data_type, filters))
        if data_type == "CombatantInfo":
            return [
                {
                    "type": "combatantinfo",
                    "intellect": 3575,
                    "gear": [{"id": 1}],
                    "auras": [{"ability": 1236616, "stacks": 1, "source": 10, "name": "Poção"}],
                }
            ]
        if data_type == "DamageTaken":
            # Golpe do chefe (source 99) no jogador e um golpe em outro jogador.
            return [
                {"type": "damage", "sourceID": 99, "targetID": 10, "abilityGameID": 1},
                {"type": "damage", "sourceID": 99, "targetID": 11, "abilityGameID": 1},
            ]
        return []


def test_damage_taken_filters_by_the_player_as_source():
    """No DamageTaken do WCL o "source" do filtro é quem recebe o dano (corrigido em 03/11)."""
    from app.wcl.fetch import fetch_fight

    client = _FakeFightClient()
    fight = fetch_fight(client, "CODE", 1, actor_id=10)

    assert ("DamageTaken", {"source_id": 10, "include_resources": True}) in client.calls
    # Na cura o filtro funciona do jeito comum: por quem recebe.
    assert ("Healing", {"target_id": 10}) in client.calls
    assert [e["targetID"] for e in fight["events"]["damage_taken"]] == [10]


def test_fight_brings_pull_stats_and_auras_and_every_death():
    """CombatantInfo: intelecto e auras do pull, sem gear nem nomes. Mortes sem filtro, porque
    o WCL ignora targetID e sourceID nelas (conferido em 03/11); o motor separa as do jogador."""
    from app.wcl.fetch import fetch_fight

    client = _FakeFightClient()
    fight = fetch_fight(client, "CODE", 1, actor_id=10)

    assert fight["player"]["combatant"] == {
        "stats": {"intellect": 3575},
        "auras": [{"ability": 1236616, "stacks": 1, "source": 10}],
    }
    assert ("Deaths", {}) in client.calls


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        (None, None),
        ({"casts": None}, None),
        ({"casts": {"data": {"entries": []}}}, None),
        ({"casts": {"data": {"entries": [{"id": 11, "activeTime": 5}]}}}, None),
        ({"casts": {"data": {"entries": [{"id": 10, "activeTime": 409950}]}}}, 409950),
    ],
)
def test_active_time_is_none_when_the_table_has_no_player(report, expected):
    """Sem o número do WCL o motor cai na conta própria (para todos, ver checks._active)."""
    from app.wcl.fetch import fetch_fight_tables

    class Client:
        def query(self, query, variables, timeout=None):
            return {"reportData": {"report": report}}

    assert fetch_fight_tables(Client(), "CODE", 1, 10)["active_time_ms"] == expected


def damage_table(entries, total_time=415_640):
    return {"damage": {"data": {"entries": entries, "totalTime": total_time}}}


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        (None, None),
        (damage_table([]), None),
        (damage_table([{"id": 11, "total": 5}]), None),
        (damage_table([{"id": 10, "total": 1000}], total_time=0), None),
        (damage_table([{"id": 10, "total": 0}]), None),
        (
            damage_table([{"id": 10, "total": 93_802_105}]),
            {"total": 93_802_105, "total_time_ms": 415_640, "rdps_taken": 0},
        ),
        (
            damage_table([{"id": 10, "total": 1_000_000, "totalRDPSTaken": 120_000}]),
            {"total": 1_000_000, "total_time_ms": 415_640, "rdps_taken": 120_000},
        ),
    ],
)
def test_official_damage_comes_from_the_damage_done_table(report, expected):
    """O DPS do ranking: total ÷ totalTime da tabela DamageDone (já sem o dano creditado ao
    Evocador, que os eventos ainda trazem)."""
    from app.wcl.fetch import fetch_fight_tables

    class Client:
        def query(self, query, variables, timeout=None):
            return {"reportData": {"report": report}}

    damage = fetch_fight_tables(Client(), "CODE", 1, 10)["damage"]
    if expected is None:
        assert damage is None
    else:
        dps = damage.pop("dps")
        assert damage == expected
        assert dps == pytest.approx(expected["total"] / expected["total_time_ms"] * 1000)


def test_tables_come_in_one_answer_with_both_aliases():
    """Casts e dano num pedido só: cada número sai da sua tabela (o activeTime da DamageDone é
    outro e não vale)."""
    from app.wcl.fetch import fetch_fight_tables

    report = {
        "casts": {"data": {"entries": [{"id": 10, "activeTime": 409_950}]}},
        "damage": {
            "data": {
                "entries": [{"id": 10, "total": 93_802_105, "activeTime": 414_004}],
                "totalTime": 415_641,
            }
        },
    }
    calls = []

    class Client:
        def query(self, query, variables, timeout=None):
            calls.append(query)
            return {"reportData": {"report": report}}

    tables = fetch_fight_tables(Client(), "CODE", 1, 10)
    assert len(calls) == 1
    assert tables["active_time_ms"] == 409_950
    assert tables["damage"]["dps"] == pytest.approx(225_680.6, abs=0.1)


def test_fight_without_combatant_info_has_no_combatant():
    from app.wcl.fetch import fetch_fight

    class NoCombatant(_FakeFightClient):
        def events(self, code, fight_id, start, end, data_type, **filters):
            return (
                []
                if data_type == "CombatantInfo"
                else super().events(code, fight_id, start, end, data_type, **filters)
            )

    assert fetch_fight(NoCombatant(), "CODE", 1, actor_id=10)["player"]["combatant"] is None
