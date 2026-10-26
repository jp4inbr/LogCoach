"""Busca de uma luta completa e dos rankings, no formato que o motor vai ler.

Os tempos ficam em ms do report, como vêm da API. Quem converte para
"segundos desde o início da fase" é o motor.
"""

from typing import Any

from app.services.players import normalize_server
from app.wcl import queries
from app.wcl.client import WclClient, WclError

MYTHIC = 5


def bracket_index(item_level: float, bracket_min: int, bucket: int) -> int:
    """Índice do bracket do WCL (começa em 1). Ex.: min 272, bucket 3 → 327 cai no 19 (326–328)."""
    return int((int(item_level) - bracket_min) // bucket) + 1


def bracket_range(index: int, bracket_min: int, bucket: int) -> tuple[int, int]:
    low = bracket_min + (index - 1) * bucket
    return low, low + bucket - 1


def find_player(actors: list[dict[str, Any]], name: str, server: str | None = None) -> dict:
    players = [a for a in actors if a["type"] == "Player" and a["name"] == name]
    if len(players) > 1 and server:
        players = [a for a in players if normalize_server(a["server"]) == normalize_server(server)]
    if len(players) != 1:
        raise WclError(f"Jogador {name!r} não encontrado (ou ambíguo) no report.")
    return players[0]


def _details_by_id(details: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    """playerDetails vem separado por função (dps, healers, tanks); aqui fica por id do ator."""
    by_role = ((details or {}).get("data") or {}).get("playerDetails") or {}
    return {
        entry["id"]: {**entry, "role": role}
        for role in ("dps", "healers", "tanks")
        for entry in by_role.get(role) or []
    }


def _player_details(details: dict[str, Any], actor_id: int) -> dict[str, Any] | None:
    return _details_by_id(details).get(actor_id)


def fetch_report(client: WclClient, code: str) -> dict[str, Any]:
    """Lutas de chefe e jogadores de um report inteiro (uma consulta só).

    Os tempos ficam em ms do report. `details` é o playerDetails somado de todas as
    lutas de chefe (specs com contagem, minItemLevel/maxItemLevel), por id do ator.
    """
    report = client.query(queries.REPORT_FIGHTS, {"code": code})["reportData"]["report"]
    if report is None:
        raise WclError(f"Report {code} não encontrado.")
    return {
        "code": report["code"],
        "title": report["title"],
        "fights": report["fights"] or [],
        "actors": [
            a for a in (report["masterData"] or {}).get("actors") or [] if a["type"] == "Player"
        ],
        "details": _details_by_id(report.get("playerDetails")),
    }


def fetch_fight(
    client: WclClient, code: str, fight_id: int, player_name: str, server: str | None = None
) -> dict[str, Any]:
    report = client.query(queries.FIGHT_META, {"code": code, "fightID": fight_id})["reportData"][
        "report"
    ]
    if not report["fights"]:
        raise WclError(f"Luta {fight_id} não existe no report {code}.")
    fight = report["fights"][0]
    actors = report["masterData"]["actors"]
    player = find_player(actors, player_name, server)
    phase_names = next(
        (p["phases"] for p in report["phases"] or [] if p["encounterID"] == fight["encounterID"]),
        [],
    )

    def events(data_type: str, **filters: Any) -> list[dict[str, Any]]:
        return client.events(
            code, fight_id, fight["startTime"], fight["endTime"], data_type, **filters
        )

    pid = player["id"]
    fight_events = {
        "casts": events("Casts", source_id=pid),
        "buffs": events("Buffs", target_id=pid),
        "damage_done": events("DamageDone", source_id=pid),
        "damage_taken": events("DamageTaken", target_id=pid),
        "deaths": events("Deaths", target_id=pid),
        "boss_casts": events("Casts", hostility_type="Enemies"),
    }
    for kind, kind_events in fight_events.items():
        for event in kind_events:
            event.pop("fight", None)
            if kind == "damage_done":
                # Lista de buffs ativos em cada golpe: já está na linha do tempo de "buffs".
                event.pop("buffs", None)

    # O masterData é do report inteiro (todas as lutas da noite); fica só o que esta luta usa.
    used_actors = {pid} | {
        e[key] for es in fight_events.values() for e in es for key in ("sourceID", "targetID")
    }
    used_actors |= {a["id"] for a in actors if a["petOwner"] == pid}
    used_abilities = {e["abilityGameID"] for es in fight_events.values() for e in es}
    actors = [a for a in actors if a["id"] in used_actors]
    abilities = [a for a in report["masterData"]["abilities"] if a["gameID"] in used_abilities]

    return {
        "meta": {
            "report": code,
            "report_start_time": report["startTime"],
            "fight": fight,
            "duration_ms": fight["endTime"] - fight["startTime"],
        },
        "phases": phase_names,
        "actors": actors,
        "abilities": abilities,
        "player": {
            "actor": player,
            "details": _player_details(report["playerDetails"], pid),
        },
        "events": fight_events,
    }


def fetch_brackets(client: WclClient, encounter_id: int) -> dict[str, Any]:
    data = client.query(queries.ENCOUNTER_BRACKETS, {"encounterID": encounter_id})
    return data["worldData"]["encounter"]["zone"]["brackets"]


def fetch_rankings(
    client: WclClient,
    encounter_id: int,
    class_name: str,
    spec_name: str,
    difficulty: int = MYTHIC,
    bracket: int | None = None,
    n: int = 10,
) -> list[dict[str, Any]]:
    """Os n primeiros por DPS. Sem bracket = ranking geral (usado no RF21)."""
    rankings: list[dict[str, Any]] = []
    page = 1
    while len(rankings) < n:
        data = client.query(
            queries.CHARACTER_RANKINGS,
            {
                "encounterID": encounter_id,
                "className": class_name,
                "specName": spec_name,
                "difficulty": difficulty,
                "bracket": bracket,
                "page": page,
            },
        )
        result = data["worldData"]["encounter"]["characterRankings"]
        rankings.extend(result["rankings"])
        if not result.get("hasMorePages"):
            break
        page += 1
    return rankings[:n]
