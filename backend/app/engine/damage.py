"""Dano por cast do próprio jogador, a base dos impactos em % (decisão de 03/11).

Cada custo usa os números do próprio log: quanto vale um Missiles, um Blast, um Bolt, um
Touch e quanto cada acúmulo de Salvo soma ao Barrage. Assim o equipamento do jogador já está
na conta e o impacto sai em % do dano dele.
"""

import bisect
from dataclasses import dataclass
from typing import Any

from app.engine.fight import amount, casts, damage_done
from app.engine.timeline import stacks_before

# Golpes do Barrage e os Meteorites que ele derruba chegam até ~3 s depois do cast.
BARRAGE_HIT_WINDOW_MS = 3000


@dataclass(frozen=True)
class CastDamage:
    missiles: float  # dano médio por cast
    blast: float
    bolt: float
    touch: float
    barrage_base: float  # Barrage (com Meteorites) ≈ base + por_salvo × acúmulos
    barrage_per_salvo: float


def _group(rules: dict[str, Any], name: str) -> dict[str, Any]:
    return rules["ability_groups"][name]


def per_cast(fight: dict[str, Any], rules: dict[str, Any], name: str) -> float:
    group = _group(rules, name)
    damage = set(group["damage"])
    total = sum(amount(e) for e in damage_done(fight, rules) if e["abilityGameID"] in damage)
    count = len(casts(fight, group["cast"]))
    return total / count if count else 0.0


def barrage_fit(fight: dict[str, Any], rules: dict[str, Any]) -> tuple[float, float]:
    """Reta do dano de cada Barrage (com os Meteorites) pelo Salvo no cast: (base, por Salvo).

    No kill de referência: ~106 mil + ~9 mil por acúmulo. A parte fixa por cast explica por que
    o custo do Barrage com pouco Salvo fora do Soul não sai daqui (é o snowball)."""
    times = [e["timestamp"] for e in casts(fight, rules["abilities"]["arcane_barrage"])]
    if len(times) < 3:
        return 0.0, 0.0
    salvo = stacks_before(fight, rules["buffs"]["arcane_salvo"], times)
    hits = set(_group(rules, "arcane_barrage")["damage"]) | set(
        _group(rules, "meteorite")["damage"]
    )
    per = [0.0] * len(times)
    for event in damage_done(fight, rules):
        if event["abilityGameID"] not in hits:
            continue
        i = bisect.bisect_right(times, event["timestamp"]) - 1
        if i >= 0 and event["timestamp"] - times[i] <= BARRAGE_HIT_WINDOW_MS:
            per[i] += amount(event)
    n = len(times)
    mean_x, mean_y = sum(salvo) / n, sum(per) / n
    var = sum((x - mean_x) ** 2 for x in salvo)
    if var == 0:
        return mean_y, 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(salvo, per, strict=True)) / var
    return mean_y - slope * mean_x, max(0.0, slope)


def cast_damage(fight: dict[str, Any], rules: dict[str, Any]) -> CastDamage:
    base, slope = barrage_fit(fight, rules)
    return CastDamage(
        missiles=per_cast(fight, rules, "arcane_missiles"),
        blast=per_cast(fight, rules, "arcane_blast"),
        bolt=per_cast(fight, rules, "prismatic_bolt"),
        touch=per_cast(fight, rules, "touch_of_the_magi"),
        barrage_base=base,
        barrage_per_salvo=slope,
    )
