"""Dano por alvo e por fase, em %: quanto foi no chefe e quanto em cada add, jogador × tops.

Bater em add não é erro (eles têm de morrer), mas o ideal é o máximo no chefe. A tabela
mostra ao usuário onde ele concentrou o dano e serve à IA para apontar padding (largar o
chefe mais que os tops). Os alvos são agrupados pelo NPC (`gameID`): todos os Restless Amani
viram uma linha só.
"""

from collections import Counter
from dataclasses import dataclass, field
from statistics import fmean
from typing import Any

from app.engine.fight import amount, damage_done, phase_at, phase_spans
from app.engine.names import npc_name

MIN_DMG_PCT = 1.0


@dataclass
class TargetPhase:
    id: int
    name: str
    damage: Counter = field(default_factory=Counter)  # gameID do alvo → dano

    @property
    def total_damage(self) -> float:
        return sum(self.damage.values())

    def pct(self, game_id: int) -> float:
        total = self.total_damage
        return 100 * self.damage[game_id] / total if total else 0.0


@dataclass(frozen=True)
class TargetProfile:
    phases: dict[int, TargetPhase]
    names: dict[int, str]  # gameID → nome


@dataclass(frozen=True)
class TargetLine:
    game_id: int
    name: str
    boss: bool
    player_pct: float
    top_pct: float | None


@dataclass(frozen=True)
class PhaseTargets:
    phase_id: int
    phase_name: str
    lines: list[TargetLine]


def target_profile(fight: dict[str, Any]) -> TargetProfile:
    spans = phase_spans(fight)
    phases: dict[int, TargetPhase] = {}
    for span in spans:
        phases.setdefault(span.id, TargetPhase(span.id, span.name))
    actors = {a["id"]: a for a in fight.get("actors") or []}
    names: dict[int, str] = {}
    for event in damage_done(fight):
        span = phase_at(spans, event["timestamp"])
        actor = actors.get(event.get("targetID"))
        if span is None or actor is None or actor.get("type") != "NPC":
            continue
        game_id = actor.get("gameID") or 0
        phases[span.id].damage[game_id] += amount(event)
        names.setdefault(game_id, npc_name(game_id, actor.get("name")))
    return TargetProfile(phases, names)


def target_table(
    player: TargetProfile,
    tops: list[TargetProfile],
    boss_ids: frozenset[int] = frozenset(),
    min_pct: float = MIN_DMG_PCT,
) -> list[PhaseTargets]:
    """Por fase do jogador: % do dano em cada alvo, ao lado da média dos tops que tiveram a
    fase. O chefe vem primeiro; depois os adds, do que mais levou dano nos tops."""
    tables = []
    for phase_id, phase in player.phases.items():
        top_phases = [t.phases[phase_id] for t in tops if phase_id in t.phases]
        top_phases = [t for t in top_phases if t.total_damage]
        names = {**{k: v for t in tops for k, v in t.names.items()}, **player.names}
        lines = []
        for game_id in set(phase.damage) | {g for t in top_phases for g in t.damage}:
            player_pct = phase.pct(game_id)
            top_pct = fmean(t.pct(game_id) for t in top_phases) if top_phases else None
            if max(player_pct, top_pct or 0.0) < min_pct:
                continue
            lines.append(
                TargetLine(
                    game_id=game_id,
                    name=names.get(game_id, str(game_id)),
                    boss=game_id in boss_ids,
                    player_pct=player_pct,
                    top_pct=top_pct,
                )
            )
        lines.sort(key=lambda line: (line.boss, line.top_pct or 0.0, line.player_pct), reverse=True)
        tables.append(PhaseTargets(phase_id, phase.name, lines))
    return tables
