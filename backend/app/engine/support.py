"""Dano que o Warcraft Logs credita a quem apoiou o jogador (Evocador Aumentação).

Os buffs do Augmentation (Ebon Might, Prescience, Shifting Sands) aumentam o dano das magias
do próprio Mago, e o WCL tira esse ganho do Mago e credita ao Evocador. Os eventos de dano
não trazem essa divisão; a tabela DamageDone filtrada pelo jogador traz, por habilidade,
quanto foi creditado (`player.damage.credited`, item 12.8).

Decisão do Arthur (04/11): o motor desconta esse crédito **só dos golpes dados com apoio**
(algum buff de `support_buffs` ativo no jogador). Em cada habilidade, os golpes com apoio
perdem a mesma fração, de modo que o total dela bate com o do WCL. Se o crédito passa do dano
feito com apoio (ou não há golpe com apoio), ele sai de todos os golpes da habilidade por
igual. Outros buffs só sobem atributos e não têm o que descontar.
"""

import bisect
from typing import Any

from app.engine.fight import amount, end_ms, start_ms


def support_windows(fight: dict[str, Any], buff_ids: frozenset[int]) -> list[tuple[float, float]]:
    """Janelas (início, fim) em ms com algum buff de apoio no jogador, já unidas.

    Por quem aplicou e por buff: com dois Evocadores, o fim do Ebon Might de um não fecha a
    janela do outro. Buff cuja primeira entrada é saída ou renovação estava ativo no pull."""
    opened: dict[tuple[int, Any], float | None] = {}
    windows: list[tuple[float, float]] = []
    events = sorted(
        (e for e in fight["events"]["buffs"] if e["abilityGameID"] in buff_ids),
        # No mesmo ms, a saída antes da entrada (como o WCL manda): a janela nova abre depois.
        key=lambda e: (e["timestamp"], e["type"] == "applybuff"),
    )
    for event in events:
        key = (event["abilityGameID"], event.get("sourceID"))
        kind = event["type"]
        if key not in opened and kind != "applybuff":
            opened[key] = start_ms(fight)  # já ativo no pull
        if kind == "applybuff":
            if opened.get(key) is None:
                opened[key] = event["timestamp"]
        elif kind == "removebuff" and opened.get(key) is not None:
            windows.append((opened[key], event["timestamp"]))
            opened[key] = None
    windows += [(begin, end_ms(fight)) for begin in opened.values() if begin is not None]
    merged: list[tuple[float, float]] = []
    for begin, end in sorted(windows):
        if merged and begin <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((begin, end))
    return merged


def _inside(windows: list[tuple[float, float]], starts: list[float], t: float) -> bool:
    i = bisect.bisect_right(starts, t) - 1
    return i >= 0 and t <= windows[i][1]


def _scaled(event: dict[str, Any], factor: float) -> dict[str, Any]:
    scaled = dict(event)
    scaled["amount"] = event.get("amount", 0) * factor
    if "absorbed" in event:
        scaled["absorbed"] = event["absorbed"] * factor
    return scaled


def without_support(
    fight: dict[str, Any], events: list[dict[str, Any]], buff_ids: frozenset[int]
) -> list[dict[str, Any]]:
    """`events` (dano do jogador) sem o crédito do Augmentation. Sem os números do WCL (luta
    antiga, jogador sem apoio), devolve os eventos como estão."""
    credited = ((fight.get("player") or {}).get("damage") or {}).get("credited") or {}
    credited = {int(k): v for k, v in credited.items() if v}
    if not credited:
        return events
    windows = support_windows(fight, buff_ids)
    starts = [w[0] for w in windows]
    supported = [
        e["abilityGameID"] in credited and _inside(windows, starts, e["timestamp"]) for e in events
    ]
    with_support: dict[int, float] = dict.fromkeys(credited, 0.0)
    totals: dict[int, float] = dict.fromkeys(credited, 0.0)
    for event, is_supported in zip(events, supported, strict=True):
        g = event["abilityGameID"]
        if g in credited:
            totals[g] += amount(event)
            if is_supported:
                with_support[g] += amount(event)
    factors: dict[int, tuple[float, float]] = {}  # (com apoio, sem apoio)
    for g, cut in credited.items():
        if with_support[g] and cut <= with_support[g]:
            factors[g] = ((with_support[g] - cut) / with_support[g], 1.0)
        elif totals[g]:
            uniform = max(0.0, totals[g] - cut) / totals[g]
            factors[g] = (uniform, uniform)
    result = []
    for event, is_supported in zip(events, supported, strict=True):
        pair = factors.get(event["abilityGameID"])
        factor = 1.0 if pair is None else pair[0 if is_supported else 1]
        result.append(event if factor == 1.0 else _scaled(event, factor))
    return result
