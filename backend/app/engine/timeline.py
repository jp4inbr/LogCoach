"""Leitura de buffs na linha do tempo de uma luta (formato de `wcl.fetch.fetch_fight`).

Buff ativo no pull (poção tomada antes, defensivo, Salvo montado) não tem `applybuff` na
luta: o primeiro evento dele já é a saída. O estado do pull (`initial_stacks`) vem do
primeiro evento de acúmulo, das auras do CombatantInfo (`player.combatant.auras`) ou, sem
elas (fixtures antigas), de o primeiro evento ser a saída do buff.
"""

from typing import Any


def pull_auras(fight: dict[str, Any]) -> dict[int, int]:
    """Buffs ativos no jogador quando a luta começou: id → acúmulos."""
    combatant = (fight.get("player") or {}).get("combatant") or {}
    return {a["ability"]: a.get("stacks") or 1 for a in combatant.get("auras") or []}


def _buff_events(fight: dict[str, Any], buff_id: int) -> list[dict[str, Any]]:
    return sorted(
        (e for e in fight["events"]["buffs"] if e["abilityGameID"] == buff_id),
        key=lambda e: e["timestamp"],
    )


def initial_stacks(fight: dict[str, Any], buff_id: int, events: list[dict] | None = None) -> int:
    """Acúmulos do buff no pull (0 = inativo).

    Um primeiro evento de acúmulo diz o número exato (removebuffstack para 7 = havia 8); fora
    isso vale a aura do pull e, sem ela, se o primeiro evento é a saída do buff."""
    events = _buff_events(fight, buff_id) if events is None else events
    first = events[0] if events else None
    if first is not None and first["type"] == "removebuffstack":
        return first.get("stack", 0) + 1
    if first is not None and first["type"] == "applybuffstack":
        return max(1, first.get("stack", 1) - 1)
    auras = pull_auras(fight)
    if buff_id in auras:
        return auras[buff_id]
    if first is None or first["type"] == "applybuff":
        return 0
    return 1  # removebuff ou refreshbuff sem entrada: estava ativo no pull


def buff_windows(fight: dict[str, Any], buff_id: int) -> list[tuple[float, float]]:
    """Janelas (início, fim) em ms do report em que o buff esteve ativo."""
    all_events = _buff_events(fight, buff_id)
    events = [e for e in all_events if e["type"] in ("applybuff", "removebuff")]
    start = (
        fight["meta"]["fight"]["startTime"] if initial_stacks(fight, buff_id, all_events) else None
    )
    windows = []
    for event in events:
        if event["type"] == "applybuff":
            start = event["timestamp"]
        elif start is not None:
            windows.append((start, event["timestamp"]))
            start = None
    if start is not None:
        windows.append((start, fight["meta"]["fight"]["endTime"]))
    return windows


def stacks_before(fight: dict[str, Any], buff_id: int, times: list[float]) -> list[int]:
    """Acúmulos do buff logo antes de cada instante (o que acontece no instante não conta)."""
    changes = _buff_events(fight, buff_id)
    stacks, current, i = [], initial_stacks(fight, buff_id, changes), 0
    for time in sorted(times):
        while i < len(changes) and changes[i]["timestamp"] < time:
            event = changes[i]
            if event["type"] == "applybuff":
                current = event.get("stack", 1)
            elif event["type"] in ("applybuffstack", "removebuffstack"):
                current = event["stack"]
            elif event["type"] == "removebuff":
                current = 0
            i += 1
        stacks.append(current)
    return stacks


def inside(time: float, windows: list[tuple[float, float]]) -> bool:
    return any(start <= time <= end for start, end in windows)


def stack_gains(fight: dict[str, Any], buff_id: int) -> int:
    """Quantas vezes o buff ganhou carga (aplicado do zero ou um acúmulo a mais). O que já
    estava ativo no pull não conta."""
    events = _buff_events(fight, buff_id)
    gains, current = 0, initial_stacks(fight, buff_id, events)
    for event in events:
        if event["type"] == "applybuff":
            gains, current = gains + 1, event.get("stack", 1)
        elif event["type"] == "applybuffstack":
            gains += event["stack"] > current
            current = event["stack"]
        elif event["type"] == "removebuffstack":
            current = event["stack"]
        elif event["type"] == "removebuff":
            current = 0
    return gains
