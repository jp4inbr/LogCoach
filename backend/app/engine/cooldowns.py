"""Arcane Surge e Touch of the Magi: usos, atrasos, combo e Surge segurado.

- Usos feitos × possíveis: possível = usar no CD desde o pull até o fim da luta.
- Atraso de cada uso: quanto depois de ficar pronto (uso anterior + CD) ele saiu.
- Combo (regra do Arthur): Touch até 3,5 s depois do Surge (pode atrasar para soltar antes
  um Barrage ou um Bolt).
- Surge segurado (03/11): mais de 10 s depois de pronto é atenção; mais de 15 s sem nada que
  case (poção, lust, Power Infusion, início de fase do `allowed_holds`) é erro. O motor lista
  o que caiu junto e a IA julga se valeu a pena.
"""

import math
from dataclasses import dataclass
from typing import Any

from app.engine.fight import (
    amount,
    casts,
    duration_s,
    end_ms,
    fight_s,
    phase_spans,
    start_ms,
)
from app.engine.timeline import buff_windows, inside


@dataclass(frozen=True)
class CooldownUse:
    time_s: float  # segundos desde o início da luta
    drift_s: float  # quanto depois de ficar pronto


@dataclass(frozen=True)
class CooldownStats:
    uses: list[CooldownUse]
    possible: int

    @property
    def missed(self) -> int:
        return max(0, self.possible - len(self.uses))

    @property
    def mean_drift_s(self) -> float:
        """Atraso médio dos usos depois do primeiro (o do pull não tem de quem atrasar)."""
        later = self.uses[1:]
        return sum(u.drift_s for u in later) / len(later) if later else 0.0


@dataclass(frozen=True)
class SurgeHold:
    time_s: float
    held_s: float
    coincides: tuple[str, ...]  # "poção", "lust", "Infusão de Poder", "início da <fase>"


@dataclass(frozen=True)
class Combo:
    surge_s: float
    touch_s: float | None  # Touch que casou com o Surge (até `max_gap_s` depois); None = não casou

    @property
    def aligned(self) -> bool:
        return self.touch_s is not None


def cooldown_stats(fight: dict[str, Any], ability_id: int, cooldown_s: float) -> CooldownStats:
    uses, ready = [], 0.0
    for event in casts(fight, ability_id):
        t = fight_s(fight, event["timestamp"])
        uses.append(CooldownUse(t, max(0.0, t - ready)))
        ready = t + cooldown_s
    return CooldownStats(uses, math.floor(duration_s(fight) / cooldown_s) + 1)


def combos(fight: dict[str, Any], rules: dict[str, Any]) -> list[Combo]:
    combo = rules["combos"][0]
    surge, touch = rules["abilities"][combo["first"]], rules["abilities"][combo["then"]]
    touches = [fight_s(fight, e["timestamp"]) for e in casts(fight, touch)]
    result = []
    for event in casts(fight, surge):
        t = fight_s(fight, event["timestamp"])
        paired = next((x for x in touches if 0 <= x - t <= combo["max_gap_s"]), None)
        result.append(Combo(t, paired))
    return result


def surge_holds(
    fight: dict[str, Any],
    surge: CooldownStats,
    rules: dict[str, Any],
    encounter: dict[str, Any] | None,
) -> list[SurgeHold]:
    """Surges que saíram mais de `warn_s` depois de prontos, com o que caiu junto."""
    limits = rules["surge_hold"]
    near = limits["coincide_s"]
    potion_id = rules["consumables"][0]["ability_id"]
    potions = [fight_s(fight, e["timestamp"]) for e in casts(fight, potion_id)]
    lust = [
        (fight_s(fight, a), fight_s(fight, b))
        for buff in rules["lust_buffs"]
        for a, b in buff_windows(fight, buff)
    ]
    infusions = [
        (fight_s(fight, a), fight_s(fight, b))
        for buff in rules["external_buffs"].values()
        for a, b in buff_windows(fight, buff)
    ]
    hold_phases = {h["phase"] for h in (encounter or {}).get("allowed_holds") or [] if "phase" in h}
    phase_starts = [
        (fight_s(fight, s.start_ms), s.name) for s in phase_spans(fight) if s.id in hold_phases
    ]

    holds = []
    for use in surge.uses:
        if use.drift_s <= limits["warn_s"]:
            continue
        t = use.time_s
        coincides = []
        if any(abs(p - t) <= near for p in potions):
            coincides.append("poção")
        if any(a - near <= t <= b for a, b in lust):
            coincides.append("lust")
        if any(a - near <= t <= b for a, b in infusions):
            coincides.append("Infusão de Poder")
        coincides += [
            f"início da {name}"
            for start, name in phase_starts
            if 0 <= t - start <= limits["error_s"]
        ]
        holds.append(SurgeHold(t, use.drift_s, tuple(coincides)))
    return holds


def surge_window_extra(fight: dict[str, Any], damage: list[dict], buff_id: int) -> float:
    """Dano a mais de uma janela de Surge, no próprio jogador: o dano dentro das janelas menos
    o que ele faria no mesmo tempo no ritmo de fora delas, dividido pelo número de janelas."""
    windows = buff_windows(fight, buff_id)
    if not windows:
        return 0.0
    inside_ms = sum(b - a for a, b in windows)
    total = sum(amount(e) for e in damage)
    within = sum(amount(e) for e in damage if inside(e["timestamp"], windows))
    outside_ms = (end_ms(fight) - start_ms(fight)) - inside_ms
    rate_outside = (total - within) / outside_ms if outside_ms > 0 else 0.0
    return max(0.0, (within - rate_outside * inside_ms) / len(windows))
