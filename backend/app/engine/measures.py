"""Tudo o que o motor mede numa luta, para o jogador e para cada top.

`measure()` lê os eventos uma vez e devolve um `FightMeasures`. É isso (e não os eventos) que
se guarda dos tops no cache de 24 h: as regras (`checks.py`) só comparam medidas.
"""

import bisect
from dataclasses import dataclass
from statistics import fmean
from typing import Any

from app.engine.abilities import AbilityProfile, ability_profile
from app.engine.arcane_soul import SoulEntry, SurgeWindow, soul_entries, surge_windows
from app.engine.context import Death, ExternalBuff, deaths, external_buffs
from app.engine.cooldowns import (
    Combo,
    CooldownStats,
    SurgeHold,
    combos,
    cooldown_stats,
    surge_holds,
    surge_window_extra,
)
from app.engine.damage import CastDamage, cast_damage
from app.engine.defensives import DamagePeak, avoidable_pct_hp_per_min, damage_peaks
from app.engine.fight import amount, casts, duration_s, fight_s, total_damage
from app.engine.potion import PotionStats, potion_stats, surge_followup_rates
from app.engine.prismatic_bolt import (
    BoltMunch,
    BoltProcs,
    bolt_munch,
    bolt_procs,
    salvo_at_barrages,
)
from app.engine.rules import load_spec_rules
from app.engine.targets import TargetProfile, target_profile
from app.engine.timeline import buff_windows, stack_gains
from app.engine.uptime import own_active_pct, wcl_active_pct

# O dano do Touch explode até ~12 s depois do cast; 15 s de folga.
TOUCH_DAMAGE_WINDOW_MS = 15_000
SALVO_CAP = 25


@dataclass(frozen=True)
class FightMeasures:
    duration_s: float
    damage: float
    surge: CooldownStats
    touch: CooldownStats
    combos: list[Combo]
    surge_holds: list[SurgeHold]
    barrages: int
    barrage_low_pct: float  # % dos Barrages com menos de 12 de Salvo
    soul: list[SoulEntry]
    soul_missing_salvo: float  # acúmulos a menos nos Barrages do Soul (entradas abaixo de 12)
    windows: list[SurgeWindow]
    bolt: BoltProcs  # luta inteira
    bolt_soul: BoltProcs  # só dentro do Arcane Soul
    munch: BoltMunch
    potions: PotionStats
    surge_followup: tuple[float, float]  # DPS nos 30 s depois do Surge × no resto
    active_wcl_pct: float | None  # régua do Warcraft Logs (None sem o número)
    active_own_pct: float  # conta própria, usada quando alguma luta não tem o do WCL
    deaths: list[Death]
    peaks: list[DamagePeak]
    avoidable_pct_hp_per_min: float  # dano de mecânica evitável, % da vida máxima por minuto
    externals: list[ExternalBuff]
    clearcasting_per_min: float
    cast: CastDamage
    surge_extra: float  # dano a mais de uma janela de Surge
    touch_damage: list[tuple[float, float]]  # (segundo do cast, dano) de cada Touch
    abilities: AbilityProfile
    targets: TargetProfile

    @property
    def dps(self) -> float:
        return self.damage / self.duration_s if self.duration_s else 0.0

    @property
    def later_windows(self) -> list[SurgeWindow]:
        """Janelas de Surge fora a de abertura (o Blast da abertura não conta)."""
        return [w for w in self.windows if not w.opener]

    @property
    def blasts_per_window(self) -> float:
        later = self.later_windows
        return fmean(w.arcane_blasts for w in later) if later else 0.0


def _touch_damage(fight: dict[str, Any], rules: dict[str, Any]) -> list[tuple[float, float]]:
    group = rules["ability_groups"]["touch_of_the_magi"]
    times = [e["timestamp"] for e in casts(fight, group["cast"])]
    damage = [0.0] * len(times)
    for event in fight["events"]["damage_done"]:
        if event["abilityGameID"] not in group["damage"]:
            continue
        i = bisect.bisect_right(times, event["timestamp"]) - 1
        if i >= 0 and event["timestamp"] - times[i] <= TOUCH_DAMAGE_WINDOW_MS:
            damage[i] += amount(event)
    return [(fight_s(fight, t), d) for t, d in zip(times, damage, strict=True)]


def _soul_missing_salvo(
    fight: dict[str, Any], rules: dict[str, Any], entries: list[SoulEntry]
) -> float:
    """Quantos acúmulos faltaram nos Barrages dentro do Soul, nas entradas abaixo do mínimo.

    Dentro do Soul o Barrage não gasta Salvo: quem entra com `e` em vez do ideal (20) solta
    todos os Barrages daquela janela com até `20 − e` acúmulos a menos (limitado a 25)."""
    soul = rules["arcane_soul"]
    windows = buff_windows(fight, soul["buff_id"])
    barrage_times = [e["timestamp"] for e in casts(fight, rules["abilities"]["arcane_barrage"])]
    salvo = salvo_at_barrages(fight, rules)
    missing = 0.0
    for (begin, end), entry in zip(windows, entries, strict=True):
        if not entry.mistake:
            continue
        lift = soul["ideal_salvo"] - entry.salvo
        for t, s in zip(barrage_times, salvo, strict=True):
            if begin <= t <= end:
                missing += min(SALVO_CAP, s + lift) - s
    return missing


def measure(
    fight: dict[str, Any],
    rules: dict[str, Any] | None = None,
    encounter: dict[str, Any] | None = None,
) -> FightMeasures:
    rules = rules or load_spec_rules()
    abilities = rules["abilities"]
    by_name = {c["name"]: c for c in rules["cooldowns"]}
    surge = cooldown_stats(fight, abilities["arcane_surge"], by_name["Arcane Surge"]["cooldown_s"])
    touch = cooldown_stats(
        fight, abilities["touch_of_the_magi"], by_name["Touch of the Magi"]["cooldown_s"]
    )
    entries = soul_entries(fight, rules)
    bolt = bolt_procs(fight, rules)
    potion = rules["consumables"][0]
    minutes = duration_s(fight) / 60
    return FightMeasures(
        duration_s=duration_s(fight),
        damage=total_damage(fight),
        surge=surge,
        touch=touch,
        combos=combos(fight, rules),
        surge_holds=surge_holds(fight, surge, rules, encounter),
        barrages=bolt.barrages,
        barrage_low_pct=bolt.below_min_pct,
        soul=entries,
        soul_missing_salvo=_soul_missing_salvo(fight, rules, entries),
        windows=surge_windows(fight, rules),
        bolt=bolt,
        bolt_soul=bolt_procs(fight, rules, soul=True),
        munch=bolt_munch(fight, rules),
        potions=potion_stats(fight, rules),
        surge_followup=surge_followup_rates(
            fight, [u.time_s for u in surge.uses], potion["duration_s"]
        ),
        active_wcl_pct=wcl_active_pct(fight, encounter),
        active_own_pct=own_active_pct(fight, rules, encounter),
        deaths=deaths(fight),
        peaks=damage_peaks(fight, rules, encounter),
        avoidable_pct_hp_per_min=avoidable_pct_hp_per_min(fight, encounter),
        externals=external_buffs(fight, rules),
        clearcasting_per_min=(
            stack_gains(fight, rules["clearcasting"]["buff_id"]) / minutes if minutes else 0.0
        ),
        cast=cast_damage(fight, rules),
        surge_extra=surge_window_extra(
            fight, fight["events"]["damage_done"], rules["surge_window"]["buff_id"]
        ),
        touch_damage=_touch_damage(fight, rules),
        abilities=ability_profile(fight, rules),
        targets=target_profile(fight),
    )
