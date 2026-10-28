"""Leitura de buffs na linha do tempo de uma luta (formato de `wcl.fetch.fetch_fight`)."""

from typing import Any


def buff_windows(fight: dict[str, Any], buff_id: int) -> list[tuple[float, float]]:
    """Janelas (início, fim) em ms do report em que o buff esteve ativo."""
    events = sorted(
        (
            e
            for e in fight["events"]["buffs"]
            if e["abilityGameID"] == buff_id and e["type"] in ("applybuff", "removebuff")
        ),
        key=lambda e: e["timestamp"],
    )
    windows, start = [], None
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
    changes = sorted(
        (e for e in fight["events"]["buffs"] if e["abilityGameID"] == buff_id),
        key=lambda e: e["timestamp"],
    )
    stacks, current, i = [], 0, 0
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
