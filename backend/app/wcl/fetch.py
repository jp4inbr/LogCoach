"""Busca de uma luta completa e dos rankings, no formato que o motor vai ler.

Os tempos ficam em ms do report, como vêm da API. Quem converte para
"segundos desde o início da fase" é o motor.
"""

from typing import Any

from app.wcl import queries
from app.wcl.client import EVENTS_TIMEOUT, WclClient, WclError
from app.wcl.players import find_player

MYTHIC = 5


def bracket_index(item_level: float, bracket_min: int, bucket: int) -> int:
    """Índice do bracket do WCL (começa em 1). Ex.: min 272, bucket 3 → 327 cai no 19 (326–328)."""
    return int((int(item_level) - bracket_min) // bucket) + 1


def bracket_range(index: int, bracket_min: int, bucket: int) -> tuple[int, int]:
    low = bracket_min + (index - 1) * bucket
    return low, low + bucket - 1


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
    """Lutas de chefe de um report (consulta leve, sem jogadores). Tempos em ms do report."""
    report = client.query(queries.REPORT_FIGHTS, {"code": code})["reportData"]["report"]
    if report is None:
        raise WclError(f"Report {code} não encontrado.")
    return {"code": report["code"], "title": report["title"], "fights": report["fights"] or []}


def fetch_fight_players(client: WclClient, code: str, fight_id: int) -> dict[str, Any]:
    """Magos de uma luta: `players` traz id, spec e item level de cada jogador da luta e
    `actors` os Magos do report (nome, reino). A spec é a da luta, não a da noite.

    Se a luta vier sem spec de algum jogador, completa com o playerDetails da luta.
    """
    variables = {"code": code, "fightID": fight_id}
    report = client.query(queries.FIGHT_PLAYERS, variables)["reportData"]["report"]
    if report is None:
        raise WclError(f"Report {code} não encontrado.")
    if not report["fights"]:
        raise WclError(f"Luta {fight_id} não existe no report {code}.")
    fight = report["fights"][0]
    ids = fight.get("friendlyPlayers") or []
    specs = fight.get("friendlySpecs") or []
    item_levels = fight.get("friendlyItemLevels") or []
    players = [
        {
            "id": pid,
            "spec": specs[i] if i < len(specs) else None,
            "item_level": item_levels[i] if i < len(item_levels) else None,
        }
        for i, pid in enumerate(ids)
    ]
    actors = [a for a in (report["masterData"] or {}).get("actors") or [] if a["type"] == "Player"]
    mages = {a["id"] for a in actors}
    if any(p["spec"] is None for p in players if p["id"] in mages):
        data = client.query(queries.FIGHT_PLAYER_DETAILS, variables)["reportData"]["report"]
        details = _details_by_id((data or {}).get("playerDetails"))
        for player in players:
            entry = details.get(player["id"])
            if player["spec"] is None and entry:
                player["spec"] = next((s["spec"] for s in entry.get("specs") or []), None)
                player["item_level"] = player["item_level"] or entry.get("maxItemLevel")
    return {"fight_id": fight["id"], "players": players, "actors": actors}


def fetch_fight(
    client: WclClient,
    code: str,
    fight_id: int,
    *,
    actor_id: int | None = None,
    name: str | None = None,
    server: str | None = None,
) -> dict[str, Any]:
    """Luta completa de um jogador: pelo id do ator (jogador analisado) ou por nome + reino
    (top 10, que o ranking traz sem id). Ver `wcl/players.py`.
    """
    # Parte da busca pesada (masterData e playerDetails de um log que pode ser do dia
    # inteiro): espera como as páginas de eventos, não como as consultas pequenas.
    variables = {"code": code, "fightID": fight_id}
    data = client.query(queries.FIGHT_META, variables, timeout=EVENTS_TIMEOUT)
    report = data["reportData"]["report"]
    if report is None:
        raise WclError(f"Report {code} não encontrado.")
    if not report["fights"]:
        raise WclError(f"Luta {fight_id} não existe no report {code}.")
    fight = report["fights"][0]
    actors = report["masterData"]["actors"]
    player = find_player(actors, actor_id=actor_id, name=name, server=server)
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
        # Em buffs, o WCL trata o dono da aura como "source": com targetID só viriam os buffs
        # que o próprio jogador lança. Com sourceID vêm também os externos (Power Infusion,
        # Bloodlust...); o filtro garante que são buffs no jogador.
        "buffs": [e for e in events("Buffs", source_id=pid) if e.get("targetID") == pid],
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
