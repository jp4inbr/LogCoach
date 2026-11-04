"""Poção (Light's Potential): a 1ª junto do primeiro lust da luta e a 2ª junto de um Surge.

Decisão de 03/11: a 1ª poção não é necessariamente no pull. Nos tops, quem teve lust tarde
não tomou poção no pull e tomou junto do lust; aí a luta pode não durar o bastante para uma
2ª, e isso não é erro. Segurar a 2ª para casar com um Surge é o recomendado. Uma poção
"casa" quando sai a até `aligned_within_s` do início de um lust ou de um Surge.
"""

from dataclasses import dataclass
from typing import Any

from app.engine.fight import amount, casts, damage_done, duration_s, fight_s
from app.engine.timeline import buff_windows, initial_stacks


@dataclass(frozen=True)
class PotionUse:
    time_s: float
    with_: str | None  # "lust", "Surto Arcano" ou None (fora de tudo)

    @property
    def aligned(self) -> bool:
        return self.with_ is not None


@dataclass(frozen=True)
class PotionStats:
    uses: list[PotionUse]
    expected: int  # quantas cabiam na luta, a partir do primeiro lust (ou do pull)
    first_lust_s: float | None
    damage_bonus: float  # dano a mais enquanto dura (intelecto da poção ÷ o do jogador)

    @property
    def missing(self) -> int:
        return max(0, self.expected - len(self.uses))

    @property
    def misaligned(self) -> int:
        return sum(not u.aligned for u in self.uses)


def lust_starts(fight: dict[str, Any], rules: dict[str, Any]) -> list[float]:
    return sorted(
        fight_s(fight, start)
        for buff in rules["lust_buffs"]
        for start, _ in buff_windows(fight, buff)
    )


def potion_stats(fight: dict[str, Any], rules: dict[str, Any]) -> PotionStats:
    potion = rules["consumables"][0]
    near = potion["aligned_within_s"]
    lusts = lust_starts(fight, rules)
    surges = [
        fight_s(fight, e["timestamp"]) for e in casts(fight, rules["abilities"]["arcane_surge"])
    ]

    times = [fight_s(fight, e["timestamp"]) for e in casts(fight, potion["ability_id"])]
    if initial_stacks(fight, potion["ability_id"]):
        # Tomada antes do pull: o cast fica fora da luta, só o buff aparece (top09, 03/11).
        # Hora estimada pela saída do buff; conta como no pull.
        windows = buff_windows(fight, potion["ability_id"])
        ends = fight_s(fight, windows[0][1]) if windows else potion["duration_s"]
        times.insert(0, min(0.0, ends - potion["duration_s"]))

    uses = []
    for t in times:
        if any(abs(t - lust) <= near for lust in lusts):
            uses.append(PotionUse(t, "lust"))
        elif any(abs(t - surge) <= near for surge in surges):
            uses.append(PotionUse(t, "Surto Arcano"))
        else:
            uses.append(PotionUse(t, None))

    # A conta parte da 1ª poção (ou, sem nenhuma, de quando ela deveria sair: o primeiro
    # lust, ou o pull se não houve lust). Cabe uma 2ª se o CD volta antes do fim da luta.
    anchor = uses[0].time_s if uses else (lusts[0] if lusts else 0.0)
    expected = 1 + int(anchor + potion["cooldown_s"] + near <= duration_s(fight))
    return PotionStats(uses, expected, lusts[0] if lusts else None, damage_bonus(fight, rules))


def damage_bonus(fight: dict[str, Any], rules: dict[str, Any]) -> float:
    """Intelecto da poção ÷ intelecto do jogador no pull (CombatantInfo). Se ele entrou na
    luta com a poção ativa, o intelecto do pull já a inclui. Sem o atributo, vale a reserva
    do YAML (19%, medida no Harmonist)."""
    potion = rules["consumables"][0]
    stats = ((fight.get("player") or {}).get("combatant") or {}).get("stats") or {}
    intellect = stats.get("intellect")
    if not intellect or not potion.get("intellect"):
        return potion["damage_bonus"]
    if initial_stacks(fight, potion["ability_id"]):
        intellect -= potion["intellect"]
    return potion["intellect"] / intellect if intellect > 0 else potion["damage_bonus"]


def surge_followup_rates(
    fight: dict[str, Any], surge_times_s: list[float], window_s: float
) -> tuple[float, float]:
    """DPS do jogador nos `window_s` depois de cada Surge e no resto da luta.

    Medido em 28/10 nas 11 fixtures: nos 30 s depois do Surge o DPS é ~37% maior. É o que
    faz a poção render mais junto do Surge."""
    windows = [(t, t + window_s) for t in surge_times_s]
    within = outside = 0.0
    for event in damage_done(fight):
        t = fight_s(fight, event["timestamp"])
        if any(a <= t < b for a, b in windows):
            within += amount(event)
        else:
            outside += amount(event)
    covered = sum(min(b, duration_s(fight)) - a for a, b in windows)
    rest = duration_s(fight) - covered
    return (within / covered if covered > 0 else 0.0, outside / rest if rest > 0 else 0.0)
