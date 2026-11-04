"""Tempo ativo: quanto da luta o jogador passou conjurando alguma coisa.

Duas réguas, e a comparação usa uma só para todos (`checks._active`):
- **Warcraft Logs** (`player.active_time_ms`, tabela de casts), a principal desde 03/11. A
  conta própria dava 93,8% no Harmonist contra 98,6% do WCL e 96,6–98,5% nos tops contra
  99,2–99,8%, quase triplicando a diferença dele. O tempo morto sai do denominador (o WCL não
  conta como ativo o tempo morto; a morte já tem regra própria). Com fase sem alvo
  (`downtime_excluded_phases`) na luta, o número do WCL é recusado: ele conta o que foi
  conjurado nela e não dá para separar.
- **Conta própria**, reserva quando falta o número do WCL em alguma luta da comparação:
  cast com tempo de conjuração ocupa do `begincast` ao `cast` (no mínimo um GCD), instantâneo
  ocupa um GCD, o Arcane Missiles ocupa até o último tick antes do cast seguinte. O GCD é
  estimado no próprio jogador e buracos de até `LATENCY_S` contam como ativos (latência).
  Tempo morto e fases sem alvo saem da conta.
Intermissão com alvo (como a do Nek'zali, com o Echo of Jawae) conta: é troca de alvo.
"""

import statistics
from typing import Any

from app.engine.context import deaths
from app.engine.fight import damage_done, end_ms, phase_spans, start_ms

# GCD do Mago: 1,5 s sem haste; com muita haste, não abaixo de 0,75 s.
GCD_MAX_S, GCD_MIN_S = 1.5, 0.75
LATENCY_S = 0.3


def estimate_gcd_s(fight: dict[str, Any], rules: dict[str, Any]) -> float:
    """Intervalo típico (mediana) entre um Barrage (instantâneo) e o cast seguinte."""
    barrage = rules["abilities"]["arcane_barrage"]
    events = sorted(
        (e for e in fight["events"]["casts"] if e["type"] in ("cast", "begincast")),
        key=lambda e: e["timestamp"],
    )
    gaps = [
        (b["timestamp"] - a["timestamp"]) / 1000
        for a, b in zip(events, events[1:], strict=False)
        if a["type"] == "cast" and a["abilityGameID"] == barrage
    ]
    gaps = [g for g in gaps if 0 < g < GCD_MAX_S * 2]
    if len(gaps) < 4:
        return GCD_MAX_S
    return min(GCD_MAX_S, max(GCD_MIN_S, statistics.median(gaps)))


def _busy_intervals(fight: dict[str, Any], rules: dict[str, Any], gcd_ms: float) -> list[list]:
    missiles_cast = rules["ability_groups"]["arcane_missiles"]["cast"]
    missiles_hits = set(rules["ability_groups"]["arcane_missiles"]["damage"])
    ticks = sorted(
        e["timestamp"] for e in damage_done(fight) if e["abilityGameID"] in missiles_hits
    )
    events = sorted(
        (e for e in fight["events"]["casts"] if e["type"] in ("cast", "begincast")),
        key=lambda e: e["timestamp"],
    )
    intervals, pending = [], {}
    for i, event in enumerate(events):
        t, ability = event["timestamp"], event["abilityGameID"]
        if event["type"] == "begincast":
            pending[ability] = t
            continue
        begin = pending.pop(ability, t)
        end = max(t, begin + gcd_ms)
        if ability == missiles_cast:
            following = next((e["timestamp"] for e in events[i + 1 :]), end_ms(fight))
            last_tick = max((x for x in ticks if t <= x <= following), default=t)
            end = max(end, last_tick)
        intervals.append([begin, end])
    return intervals


def _excluded(fight: dict[str, Any], encounter: dict[str, Any] | None) -> tuple[list, list]:
    """(tempo morto, fases sem alvo), em ms do report."""
    start = start_ms(fight)
    dead = [[start + d.time_s * 1000, start + (d.time_s + d.dead_s) * 1000] for d in deaths(fight)]
    skip = set((encounter or {}).get("downtime_excluded_phases") or [])
    phases = [[s.start_ms, s.end_ms] for s in phase_spans(fight) if s.id in skip]
    return dead, phases


def _clip(fight: dict[str, Any], intervals: list[list], tolerance_ms: float = 0.0) -> list[list]:
    """Intervalos cortados à luta e unidos (com folga de `tolerance_ms`)."""
    start, end = start_ms(fight), end_ms(fight)
    merged: list[list] = []
    for a, b in sorted([max(a, start), min(b, end)] for a, b in intervals):
        if b <= a:
            continue
        if merged and a <= merged[-1][1] + tolerance_ms:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def wcl_active_pct(fight: dict[str, Any], encounter: dict[str, Any] | None = None) -> float | None:
    """Tempo ativo do Warcraft Logs sobre o tempo vivo; None sem o número ou com fase sem alvo."""
    active = (fight.get("player") or {}).get("active_time_ms")
    dead, phases = _excluded(fight, encounter)
    if active is None or _clip(fight, phases):
        return None
    counted = (end_ms(fight) - start_ms(fight)) - sum(b - a for a, b in _clip(fight, dead))
    return 100.0 if counted <= 0 else 100 * min(1.0, active / counted)


def own_active_pct(
    fight: dict[str, Any], rules: dict[str, Any], encounter: dict[str, Any] | None = None
) -> float:
    """Conta própria (reserva)."""
    dead, phases = _excluded(fight, encounter)
    out = _clip(fight, dead + phases)
    counted = (end_ms(fight) - start_ms(fight)) - sum(b - a for a, b in out)
    if counted <= 0:
        return 100.0
    gcd_ms = estimate_gcd_s(fight, rules) * 1000
    busy = _clip(fight, _busy_intervals(fight, rules, gcd_ms), LATENCY_S * 1000)
    # Ocupado dentro de trecho excluído não conta (nem para mais, nem para menos).
    busy_in_out = sum(max(0.0, min(b, d) - max(a, c)) for a, b in busy for c, d in out)
    active = sum(b - a for a, b in busy) - busy_in_out
    return 100 * min(1.0, active / counted)


def active_time_pct(
    fight: dict[str, Any], rules: dict[str, Any], encounter: dict[str, Any] | None = None
) -> float:
    """O número do WCL quando existe; senão, a conta própria. Para comparar lutas, use as duas
    réguas separadas (`checks._active`)."""
    wcl = wcl_active_pct(fight, encounter)
    return wcl if wcl is not None else own_active_pct(fight, rules, encounter)
