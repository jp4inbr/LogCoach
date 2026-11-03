"""Tempo ativo: quanto da luta o jogador passou conjurando alguma coisa.

A régua é o "Active Time" do Warcraft Logs (`player.active_time_ms`, tabela de casts), desde
03/11: a conta própria abaixo dava 93,8% no Harmonist contra 98,6% do WCL e 96,6–98,5% nos
tops contra 99,2–99,8%, quase triplicando a diferença dele. Do número do WCL saem o tempo
morto e as fases sem alvo (o WCL não conta como ativo o tempo morto, então ficar morto não
pesa duas vezes: a morte já tem regra própria).

A conta própria fica de reserva para lutas sem o número do WCL (fixtures antigas). O limite
não é fixo (03/11): o tempo ativo é comparado com a mediana dos tops. Por isso a
conta só precisa ser a mesma para todos, não idêntica à do Warcraft Logs:
- cast com tempo de conjuração: ocupado do `begincast` ao `cast` (no mínimo um GCD);
- instantâneo: ocupado por um GCD;
- canal (Arcane Missiles): ocupado até o último tick antes do cast seguinte.
O GCD é estimado no próprio jogador (haste muda de um para outro), e buracos de até
`LATENCY_S` entre um cast e outro contam como ativos (latência e fila de comando, não tempo
parado). Medido em 03/11 nas fixtures: tops de 96,6% a 98,5%, perto do que o Warcraft Logs
mostra; sem a tolerância, metade do "tempo parado" eram buracos de 0,1 a 0,3 s. Tempo morto e
fases sem
nada para bater (`downtime_excluded_phases` do encontro) saem da conta. Intermissão com alvo
(como a do Nek'zali, com o Echo of Jawae) conta: é troca de alvo, não tempo parado.
"""

import statistics
from typing import Any

from app.engine.context import deaths
from app.engine.fight import end_ms, phase_spans, start_ms

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
        e["timestamp"]
        for e in fight["events"]["damage_done"]
        if e["abilityGameID"] in missiles_hits
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


def active_time_pct(
    fight: dict[str, Any], rules: dict[str, Any], encounter: dict[str, Any] | None = None
) -> float:
    start, end = start_ms(fight), end_ms(fight)

    excluded = [
        [start + d.time_s * 1000, start + (d.time_s + d.dead_s) * 1000] for d in deaths(fight)
    ]
    skip = set((encounter or {}).get("downtime_excluded_phases") or [])
    excluded += [[s.start_ms, s.end_ms] for s in phase_spans(fight) if s.id in skip]

    def clip(intervals: list[list], tolerance_ms: float = 0.0) -> list[list]:
        merged: list[list] = []
        for a, b in sorted([max(a, start), min(b, end)] for a, b in intervals):
            if b <= a:
                continue
            if merged and a <= merged[-1][1] + tolerance_ms:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        return merged

    out = clip(excluded)
    counted = (end - start) - sum(b - a for a, b in out)
    if counted <= 0:
        return 100.0
    wcl_active = (fight.get("player") or {}).get("active_time_ms")
    if wcl_active is not None:
        return 100 * min(1.0, wcl_active / counted)

    gcd_ms = estimate_gcd_s(fight, rules) * 1000
    busy = clip(_busy_intervals(fight, rules, gcd_ms), LATENCY_S * 1000)
    # Ocupado dentro de trecho excluído não conta (nem para mais, nem para menos).
    busy_in_out = sum(max(0.0, min(b, d) - max(a, c)) for a, b in busy for c, d in out)
    active = sum(b - a for a, b in busy) - busy_in_out
    return 100 * min(1.0, active / counted)
