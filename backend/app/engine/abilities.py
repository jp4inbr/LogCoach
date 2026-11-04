"""Tabela por habilidade e por fase (RF22): casts por minuto e % do dano, jogador × tops.

Vale para qualquer habilidade, com ou sem regra própria. Tudo em taxa (por minuto) e em %,
nunca em número bruto: a duração das fases muda entre kills e o equipamento muda o dano.

Cada luta vira um *perfil* (`ability_profile`), que é o que se guarda dos tops no cache;
`ability_table` junta o perfil do jogador com os dos tops.
"""

from collections import Counter
from dataclasses import dataclass, field
from statistics import fmean
from typing import Any

from app.engine.fight import amount, casts, damage_done, phase_at, phase_spans
from app.engine.names import spell_name, wcl_ability_names
from app.engine.rules import load_spec_rules

# Linhas com menos que isso do dano (no jogador e nos tops) ficam fora da tabela.
MIN_DMG_PCT = 1.0


@dataclass
class PhaseProfile:
    id: int
    name: str
    duration_s: float = 0.0
    casts: Counter = field(default_factory=Counter)  # chave da linha → casts
    damage: Counter = field(default_factory=Counter)  # chave da linha → dano

    @property
    def total_damage(self) -> float:
        return sum(self.damage.values())


@dataclass(frozen=True)
class AbilityProfile:
    phases: dict[int, PhaseProfile]  # na ordem em que as fases aparecem na luta
    names: dict[int, str]  # chave da linha → nome
    cast_keys: frozenset[int]  # linhas que têm cast (as outras ficam sem casts/min)


@dataclass(frozen=True)
class AbilityLine:
    key: int  # ID do cast (ou do 1º de dano)
    name: str
    player_cpm: float | None
    top_cpm: float | None
    player_dmg_pct: float
    top_dmg_pct: float | None


@dataclass(frozen=True)
class PhaseAbilities:
    phase_id: int
    phase_name: str
    lines: list[AbilityLine]


def _keys(rules: dict[str, Any]) -> tuple[dict[int, int], dict[int, int]]:
    """ID de cast → chave e ID de dano → chave, pelos `ability_groups` do YAML."""
    by_cast, by_damage = {}, {}
    for group in (rules.get("ability_groups") or {}).values():
        key = group.get("cast") or group["damage"][0]
        if group.get("cast"):
            by_cast[group["cast"]] = key
        for damage_id in group.get("damage") or []:
            by_damage[damage_id] = key
    return by_cast, by_damage


def ability_profile(fight: dict[str, Any], rules: dict[str, Any] | None = None) -> AbilityProfile:
    rules = rules or load_spec_rules()
    by_cast, by_damage = _keys(rules)
    spans = phase_spans(fight)
    phases: dict[int, PhaseProfile] = {}
    for span in spans:
        phase = phases.setdefault(span.id, PhaseProfile(span.id, span.name))
        phase.duration_s += span.duration_s

    cast_keys = set()
    for event in casts(fight):
        span = phase_at(spans, event["timestamp"])
        if span is not None:
            key = by_cast.get(event["abilityGameID"], event["abilityGameID"])
            phases[span.id].casts[key] += 1
            cast_keys.add(key)
    for event in damage_done(fight):
        span = phase_at(spans, event["timestamp"])
        if span is not None:
            key = by_damage.get(event["abilityGameID"], event["abilityGameID"])
            phases[span.id].damage[key] += amount(event)

    wcl = wcl_ability_names(fight)
    keys = {k for p in phases.values() for k in (*p.casts, *p.damage)}
    names = {key: spell_name(key, wcl.get(key)) for key in keys}
    return AbilityProfile(phases, names, frozenset(cast_keys))


def _cpm(phase: PhaseProfile, key: int) -> float:
    return phase.casts[key] / (phase.duration_s / 60) if phase.duration_s else 0.0


def _dmg_pct(phase: PhaseProfile, key: int) -> float:
    total = phase.total_damage
    return 100 * phase.damage[key] / total if total else 0.0


def ability_table(
    player: AbilityProfile, tops: list[AbilityProfile], min_pct: float = MIN_DMG_PCT
) -> list[PhaseAbilities]:
    """Por fase do jogador: cada habilidade com casts/min e % do dano, ao lado da média dos
    tops que tiveram a fase. Ordenada pelo % do dano dos tops (o que mais pesa primeiro)."""
    tables = []
    for phase_id, phase in player.phases.items():
        top_phases = [t.phases[phase_id] for t in tops if phase_id in t.phases]
        keys = set(phase.damage) | {k for t in top_phases for k in t.damage}
        cast_keys = player.cast_keys.union(*(t.cast_keys for t in tops))
        names = {**{k: v for t in tops for k, v in t.names.items()}, **player.names}
        lines = []
        for key in keys:
            player_pct = _dmg_pct(phase, key)
            top_pct = fmean(_dmg_pct(t, key) for t in top_phases) if top_phases else None
            if max(player_pct, top_pct or 0.0) < min_pct:
                continue
            has_cast = key in cast_keys
            lines.append(
                AbilityLine(
                    key=key,
                    name=names.get(key, str(key)),
                    player_cpm=_cpm(phase, key) if has_cast else None,
                    top_cpm=(
                        fmean(_cpm(t, key) for t in top_phases) if has_cast and top_phases else None
                    ),
                    player_dmg_pct=player_pct,
                    top_dmg_pct=top_pct,
                )
            )
        lines.sort(key=lambda line: (line.top_dmg_pct or 0.0, line.player_dmg_pct), reverse=True)
        tables.append(PhaseAbilities(phase_id, phase.name, lines))
    return tables
