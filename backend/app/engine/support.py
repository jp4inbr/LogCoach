"""Dano que o Warcraft Logs credita a quem apoiou o jogador (Evocador Aumentação).

Os buffs do Augmentation (Ebon Might, Prescience, Shifting Sands) aumentam o dano das magias
do próprio Mago, e o WCL tira esse ganho do Mago e credita ao Evocador. Os eventos de dano
não trazem essa divisão; a tabela DamageDone filtrada pelo jogador traz, por habilidade e por
buff, quanto foi creditado (`player.damage.credited`: {habilidade: {buff: crédito}}, 12.8).

Decisão do Arthur (04/11), **desconto por buff**: em cada habilidade, cada buff tem uma taxa
(crédito dele ÷ dano da habilidade feito com ele ativo), e cada golpe perde a soma das taxas
dos buffs ativos naquele instante. O total de cada habilidade bate com o do WCL. O Ebon Might
cobre ~96% da luta, mas o Shifting Sands (crédito ~10% por golpe) só ~26%: juntar as janelas
espalhava o crédito do Sands pela luta inteira e descontava de menos no burst do Surge.

Exceções:
- habilidades de `support_uniform_abilities` (Touch of the Magi): o crédito vem do dano que
  alimentou o Touch, não do buff na explosão; sai de todos os golpes por igual;
- buff sem golpe da habilidade sob ele, ou crédito sem buff identificado: sai de todos os
  golpes da habilidade por igual.
Outros buffs só sobem atributos e não têm o que descontar.
"""

import bisect
import logging
from typing import Any

from app.engine.fight import amount, end_ms, start_ms

logger = logging.getLogger(__name__)

# Taxa máxima de um buff sobre o dano sob ele. Nas fixtures o maior é ~11% (Shifting Sands);
# acima disso, a janela e a atribuição do WCL não casam (golpe na borda, pet logo depois da
# saída do buff) e o que passar sai de todos os golpes da habilidade por igual.
MAX_BUFF_RATE = 0.5


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


def _credits(fight: dict[str, Any]) -> dict[int, dict[int, float]]:
    """{habilidade: {buff: crédito}}. Crédito sem buff identificado vai no buff 0. Aceita o
    formato antigo {habilidade: crédito} (cópias de 04/11), que vira buff 0: desconto por
    igual em todos os golpes da habilidade, sem separar o burst."""
    raw = ((fight.get("player") or {}).get("damage") or {}).get("credited") or {}
    credits: dict[int, dict[int, float]] = {}
    for ability, value in raw.items():
        by_buff = value if isinstance(value, dict) else {"0": value}
        by_buff = {int(b): v for b, v in by_buff.items() if v}
        if by_buff:
            credits[int(ability)] = by_buff
    return credits


def without_support(
    fight: dict[str, Any],
    events: list[dict[str, Any]],
    buff_ids: frozenset[int],
    uniform: frozenset[int] = frozenset(),
) -> list[dict[str, Any]]:
    """`events` (dano do jogador) sem o crédito do Augmentation. Sem os números do WCL (luta
    antiga, jogador sem apoio), devolve os eventos como estão. `uniform`: habilidades com o
    crédito tirado de todos os golpes por igual (Touch)."""
    credits = _credits(fight)
    if not credits:
        return events
    buffs = {b for by_buff in credits.values() for b in by_buff if b in buff_ids}
    windows = {b: support_windows(fight, frozenset({b})) for b in buffs}
    starts = {b: [w[0] for w in ws] for b, ws in windows.items()}
    active = [
        frozenset(b for b in buffs if _inside(windows[b], starts[b], e["timestamp"]))
        if e["abilityGameID"] in credits
        else frozenset()
        for e in events
    ]
    # Dano de cada habilidade sob cada buff, e no total.
    under: dict[tuple[int, int], float] = {}
    totals: dict[int, float] = {}
    for event, on in zip(events, active, strict=True):
        g = event["abilityGameID"]
        if g not in credits:
            continue
        totals[g] = totals.get(g, 0.0) + amount(event)
        for b in on:
            under[g, b] = under.get((g, b), 0.0) + amount(event)
    # Por habilidade: taxa de cada buff sobre o dano sob ele, e a parte que sai por igual.
    rates: dict[int, dict[int, float]] = {}
    flat: dict[int, float] = {}
    for g, by_buff in credits.items():
        if not totals.get(g):
            # Id da tabela sem eventos: o total do motor fica acima do oficial.
            logger.warning("Crédito ao Evocador na habilidade %s sem eventos: %s", g, by_buff)
            continue
        rates[g] = {}
        spread = 0.0
        for b, cut in by_buff.items():
            if g in uniform or not under.get((g, b)):
                spread += cut
                continue
            rate = min(cut / under[g, b], MAX_BUFF_RATE)
            rates[g][b] = rate
            spread += cut - rate * under[g, b]
        flat[g] = spread / totals[g]
    result = []
    for event, on in zip(events, active, strict=True):
        g = event["abilityGameID"]
        if g not in rates:
            result.append(event)
            continue
        cut = flat[g] + sum(rates[g].get(b, 0.0) for b in on)
        result.append(_scaled(event, max(0.0, 1.0 - cut)) if cut else event)
    return result
