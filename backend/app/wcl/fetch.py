"""Busca de uma luta completa e dos rankings, no formato que o motor vai ler.

Os tempos ficam em ms do report, como vêm da API. Quem converte para
"segundos desde o início da fase" é o motor.
"""

from typing import Any

from app.wcl import queries
from app.wcl.client import EVENTS_TIMEOUT, WclClient, WclError
from app.wcl.players import find_player

MYTHIC = 5


class FightNotFoundError(WclError):
    """O report existe, mas não tem a luta pedida."""


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


# Campos do dano recebido e da cura que o motor usa. Com includeResources o WCL manda também
# posição, armadura, poder de ataque etc. de cada golpe; fora daqui, só pesariam nas fixtures.
TAKEN_FIELDS = (
    "timestamp", "type", "sourceID", "targetID", "abilityGameID", "amount", "absorbed",
    "mitigated", "unmitigatedAmount", "overkill", "hitType", "tick", "isAoE", "buffs",
    "hitPoints", "maxHitPoints",
)  # fmt: skip
HEAL_FIELDS = (
    "timestamp", "type", "sourceID", "targetID", "abilityGameID", "amount", "overheal",
    "absorbed", "tick",
)  # fmt: skip


def _slim_taken(event: dict[str, Any]) -> dict[str, Any]:
    return {k: event[k] for k in TAKEN_FIELDS if k in event}


def _slim_heal(event: dict[str, Any]) -> dict[str, Any]:
    return {k: event[k] for k in HEAL_FIELDS if k in event}


# Atributos do CombatantInfo que o motor pode usar; gear e talentos ficam de fora do arquivo.
COMBATANT_STATS = ("intellect", "critSpell", "hasteSpell", "mastery", "versatilityDamageDone")


def _combatant(event: dict[str, Any] | None) -> dict[str, Any] | None:
    """Atributos e auras do jogador no pull (evento CombatantInfo).

    As auras ajudam a saber o que já estava ativo quando a luta começou, mas vêm incompletas
    (03/11: sem Prismatic Barrier, Mirror Image nem a poção tomada antes do pull); o motor
    completa pelo primeiro evento de cada buff (`engine/timeline.initial_stacks`).
    """
    if not event:
        return None
    return {
        "stats": {k: event[k] for k in COMBATANT_STATS if k in event},
        "auras": [
            {"ability": a["ability"], "stacks": a.get("stacks", 1), "source": a.get("source")}
            for a in event.get("auras") or []
            if "ability" in a
        ],
    }


def fetch_active_time_ms(client: WclClient, code: str, fight_id: int, actor_id: int) -> int | None:
    """Tempo ativo do jogador como o Warcraft Logs mostra (tabela de casts, `activeTime`).

    A conta própria (`engine/uptime.py`) dava 93,8% no Harmonist contra 98,6% do WCL (03/11);
    o número do WCL vira a régua e a conta própria fica de reserva."""
    data = client.query(
        queries.FIGHT_ACTIVE_TIME, {"code": code, "fightID": fight_id}, timeout=EVENTS_TIMEOUT
    )
    table = (((data["reportData"]["report"] or {}).get("table") or {}).get("data")) or {}
    entry = next((e for e in table.get("entries") or [] if e.get("id") == actor_id), None)
    return entry.get("activeTime") if entry else None


def fetch_report(client: WclClient, code: str) -> dict[str, Any]:
    """Lutas de chefe de um report (consulta leve, sem jogadores). Tempos em ms do report.

    `end_time` é o `endTime` do report (ms desde 1970): hora do último evento recebido, que
    num log ao vivo avança enquanto chegam dados.
    """
    report = client.query(queries.REPORT_FIGHTS, {"code": code})["reportData"]["report"]
    if report is None:
        raise WclError(f"Report {code} não encontrado.")
    return {
        "code": report["code"],
        "title": report["title"],
        "end_time": report.get("endTime"),
        "fights": report["fights"] or [],
    }


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
        raise FightNotFoundError(f"Luta {fight_id} não existe no report {code}.")
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
        raise FightNotFoundError(f"Luta {fight_id} não existe no report {code}.")
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
    # Antes dos eventos: se esta consulta pequena falhar, não se perdem os ~12 pontos deles.
    active_time_ms = fetch_active_time_ms(client, code, fight_id, pid)
    combatant = events("CombatantInfo", source_id=pid)
    fight_events = {
        "casts": events("Casts", source_id=pid),
        # Em buffs, o WCL trata o dono da aura como "source": com targetID só viriam os buffs
        # que o próprio jogador lança. Com sourceID vêm também os externos (Power Infusion,
        # Bloodlust...); o filtro garante que são buffs no jogador.
        "buffs": [e for e in events("Buffs", source_id=pid) if e.get("targetID") == pid],
        "damage_done": events("DamageDone", source_id=pid),
        # Em DamageTaken vale a mesma convenção: o "source" do filtro é quem recebe o dano.
        # Com targetID vinha só o dano que o próprio jogador causou nele mesmo (Refraction),
        # sem nenhum golpe do chefe (corrigido em 03/11). Os eventos continuam com o
        # atacante em sourceID e o jogador em targetID.
        # Com a vida do jogador depois de cada golpe (`hitPoints`/`maxHitPoints`), para os picos
        # de dano; dos recursos ficam só esses dois (ver `_slim_taken`).
        "damage_taken": [
            _slim_taken(e)
            for e in events("DamageTaken", source_id=pid, include_resources=True)
            if e.get("targetID") == pid
        ],
        # Cura recebida: aqui o filtro funciona do jeito comum, por targetID (conferido em
        # 03/11; com sourceID viria só a cura do próprio jogador nele mesmo).
        "healing_taken": [_slim_heal(e) for e in events("Healing", target_id=pid)],
        # Em Deaths o WCL ignora os filtros (com targetID vinham as mortes da raide inteira e
        # com sourceID nada, conferido em 03/11): vêm todas e o motor separa as do jogador.
        "deaths": events("Deaths"),
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
            "combatant": _combatant(combatant[0] if combatant else None),
            "active_time_ms": active_time_ms,
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
