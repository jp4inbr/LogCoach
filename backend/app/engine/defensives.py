"""Defensivo: uma política por encontro (`defensive_policy` no YAML do chefe).

Padrão geral (03/11): overlaps de mecânicas e mecânicas que miram o jogador. No Nek'zali, o
1º chefe, só os overlaps: duas mecânicas batendo no jogador em até `overlap_window_s`. Um
overlap conta como coberto se algum defensivo do Mago (buffs em `defensives` do YAML da spec)
estava ativo ou entrou na janela. É risco, não perda de dano: não tem `impact_pct`.

Cada overlap vale só na fase dele (`phase` do YAML, id do Warcraft Logs): sem isso o
Harmonist tinha 12 picos, com ele 6 (03/11). Overlaps diferentes que caem no mesmo pico contam
uma vez só, com o nome do primeiro (no Nek'zali hoje eles estão em fases diferentes).
"""

from dataclasses import dataclass
from typing import Any

from app.engine.fight import fight_s, phase_at, phase_spans
from app.engine.timeline import buff_windows


@dataclass(frozen=True)
class OverlapHit:
    name: str
    time_s: float
    defended: bool


def overlap_hits(
    fight: dict[str, Any], rules: dict[str, Any], encounter: dict[str, Any] | None
) -> list[OverlapHit]:
    if not encounter or encounter.get("defensive_policy") != "overlaps":
        return []
    window = encounter.get("overlap_window_s", 4) * 1000
    defenses = [w for d in rules["defensives"] for w in buff_windows(fight, d["buff_id"])]
    taken = fight["events"].get("damage_taken") or []
    spans = phase_spans(fight)

    def in_phase(timestamp: float, phase: int | None) -> bool:
        if phase is None:
            return True
        span = phase_at(spans, timestamp)
        return span is not None and span.id == phase

    peaks: list[tuple[float, str]] = []
    for overlap in encounter.get("overlaps") or []:
        if overlap.get("personal") or len(overlap.get("abilities") or []) < 2:
            continue  # o pessoal (Essence Rend) ainda não foi medido (TODO no YAML)
        first, second = overlap["abilities"][:2]
        phase = overlap.get("phase")
        times_a = sorted(
            e["timestamp"]
            for e in taken
            if e["abilityGameID"] == first and in_phase(e["timestamp"], phase)
        )
        times_b = sorted(
            e["timestamp"]
            for e in taken
            if e["abilityGameID"] == second and in_phase(e["timestamp"], phase)
        )
        last = None
        for t in times_a:
            partner = next((u for u in times_b if abs(u - t) <= window), None)
            if partner is None:
                continue
            moment = min(t, partner)
            if last is not None and moment - last <= 2 * window:
                continue  # mesmo pico: os golpes de um overlap chegam em vários ticks
            last = moment
            peaks.append((moment, overlap["name"]))

    hits, previous = [], None
    for moment, name in sorted(peaks):
        if previous is not None and moment - previous <= window:
            continue  # mesmo pico já contado por outro overlap
        previous = moment
        defended = any(a <= moment + window and b >= moment - window for a, b in defenses)
        hits.append(OverlapHit(name, fight_s(fight, moment), defended))
    return hits
