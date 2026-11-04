"""Picos de dano: de onde veio, se um defensivo cabia ou se faltou cura (decisão de 03/11).

O motor acha os picos no próprio log em vez de procurar combinações fixas de mecânicas:
- **pico** = perder `damage_pct_hp`% da vida máxima em `window_s` (dano depois da mitigação,
  contando o que escudos absorveram) **ou** ficar abaixo de `low_hp_pct`% de vida. Os dois
  limites ficam em `peaks` do YAML do encontro;
- para cada pico: as mecânicas (com a classe do YAML: evitável, alvo escolhido, função
  atribuída ou dano de raide), a vida mínima, o defensivo ativo ou pronto, a cura recebida
  logo depois e quanto tempo a vida ficou baixa;
- **veredito**: `evitavel` (a maior parte do dano era evitável: o erro é de posicionamento),
  `defensivo` (a vida caiu abaixo de `danger_hp_pct`%, sem defensivo ativo e com um pronto),
  `cura` (vida baixa por vários segundos com pouca cura: o problema é da cura, não do Mago)
  ou `ok` (inclusive quando a cura segurou o pico: nas fixtures de 03/11 a vida mínima ficou
  acima de 50% na maioria dos picos, e os tops quase não usam defensivo).
É risco, não perda de dano: não tem `impact_pct`. A explicação ao jogador fica com a IA, a
partir destes fatos.

Vida: `hitPoints`/`maxHitPoints` de cada golpe (o WCL manda com `includeResources`). Entre um
golpe e outro, a cura recebida soma à vida (até o máximo). Sem a vida no log (fixtura antiga),
não há picos.
"""

import statistics
from dataclasses import dataclass
from typing import Any, Literal

from app.engine.fight import duration_s, fight_s, phase_at, phase_spans
from app.engine.names import spell_name, wcl_ability_names
from app.engine.timeline import buff_windows

Verdict = Literal["evitavel", "defensivo", "cura", "ok"]
MechanicClass = Literal["avoidable", "targeted", "assigned", "raid", "unknown"]

DEFAULT_PEAKS = {
    "window_s": 4,
    "damage_pct_hp": 60,
    "low_hp_pct": 35,
    "heal_window_s": 5,
    "low_hp_s": 3,
    "low_heal_pct_hp": 20,
    "avoidable_share": 0.5,
    "danger_hp_pct": 50,
}


@dataclass(frozen=True)
class MechanicShare:
    ability_id: int
    name: str  # pt-BR quando houver
    mechanic_class: MechanicClass
    damage: float
    share: float  # fração do dano do pico


@dataclass(frozen=True)
class DamagePeak:
    time_s: float  # início da janela, em segundos da luta
    phase: str
    damage: float
    damage_pct_hp: float  # dano da janela em % da vida máxima
    min_hp_pct: float
    mechanics: tuple[MechanicShare, ...]
    defensive_active: str | None
    defensives_ready: tuple[str, ...]
    heal_pct_hp: float  # cura recebida da janela até `heal_window_s` depois, em % da vida
    low_hp_s: float  # tempo abaixo de `low_hp_pct` no mesmo trecho
    low_heal: bool  # vida baixa por muito tempo com pouca cura
    verdict: Verdict

    @property
    def avoidable_share(self) -> float:
        return sum(m.share for m in self.mechanics if m.mechanic_class == "avoidable")


def peak_settings(encounter: dict[str, Any] | None) -> dict[str, float]:
    return {**DEFAULT_PEAKS, **((encounter or {}).get("peaks") or {})}


def mechanic_classes(encounter: dict[str, Any] | None) -> dict[int, MechanicClass]:
    return {m["ability_id"]: m["class"] for m in (encounter or {}).get("mechanics") or []}


def _amount(event: dict[str, Any]) -> float:
    return event.get("amount", 0) + event.get("absorbed", 0)


def _taken(fight: dict[str, Any]) -> list[dict[str, Any]]:
    """Dano recebido de outros (sem o Refraction do próprio Mago), em ordem."""
    pid = fight["player"]["actor"]["id"]
    return sorted(
        (e for e in fight["events"].get("damage_taken") or [] if e.get("sourceID") != pid),
        key=lambda e: e["timestamp"],
    )


def max_hp(fight: dict[str, Any]) -> float | None:
    values = [
        e["maxHitPoints"]
        for e in fight["events"].get("damage_taken") or []
        if e.get("maxHitPoints")
    ]
    return statistics.median(values) if values else None


def _hp_series(fight: dict[str, Any], top: float) -> list[tuple[float, float]]:
    """(instante, vida) depois de cada golpe (o valor do log) e de cada cura (soma até o teto)."""
    heals = fight["events"].get("healing_taken") or []
    events = sorted(
        [(e["timestamp"], 0, e) for e in fight["events"].get("damage_taken") or []]
        + [(e["timestamp"], 1, e) for e in heals],
        key=lambda x: (x[0], x[1]),
    )
    series, hp = [], top
    for t, kind, e in events:
        if kind == 0:
            if e.get("hitPoints") is None:
                continue
            hp = e["hitPoints"]
        else:
            hp = min(top, hp + e.get("amount", 0))
        series.append((t, hp))
    return series


def _time_below(series: list[tuple[float, float]], limit: float, a: float, b: float) -> float:
    """Segundos em [a, b] com a vida abaixo de `limit` (a vida vale até a próxima mudança)."""
    total, hp = 0.0, None
    previous = a
    for t, value in series:
        if t <= a:
            hp = value
            continue
        if t >= b:
            break
        if hp is not None and hp < limit:
            total += t - previous
        previous, hp = t, value
    if hp is not None and hp < limit:
        total += b - previous
    return total / 1000


def _available_defensives(fight: dict[str, Any], rules: dict[str, Any]) -> list[dict[str, Any]]:
    """Defensivos que o jogador tem: os de todo Arcano e os que ele usou na luta (talento)."""
    used = {e["abilityGameID"] for e in fight["events"]["casts"] if e["type"] == "cast"}
    return [d for d in rules["defensives"] if d.get("baseline") or d["ability_id"] in used]


def _ready(fight: dict[str, Any], defensive: dict[str, Any], at: float) -> bool:
    last = max(
        (
            e["timestamp"]
            for e in fight["events"]["casts"]
            if e["type"] == "cast"
            and e["abilityGameID"] == defensive["ability_id"]
            and e["timestamp"] <= at
        ),
        default=None,
    )
    return last is None or at - last >= defensive.get("cooldown_s", 0) * 1000


def _peak_starts(taken: list[dict], top: float, cfg: dict[str, float]) -> list[float]:
    """Início da janela de cada pico: o trecho de `window_s` com mais dano em cada grupo de
    janelas acima do limite (ou terminando num golpe que deixou a vida baixa). Candidatos a
    até `window_s + heal_window_s` um do outro são o mesmo incidente."""
    window = cfg["window_s"] * 1000
    damage_limit = cfg["damage_pct_hp"] / 100 * top
    low_limit = cfg["low_hp_pct"] / 100 * top
    times = [e["timestamp"] for e in taken]

    def window_damage(start: float) -> float:
        return sum(_amount(e) for e in taken if start <= e["timestamp"] < start + window)

    candidates = [t for t in times if window_damage(t) >= damage_limit]
    # Vida baixa: a janela começa no primeiro golpe dos `window_s` que levaram até ela.
    candidates += [
        next(t for t in times if t > e["timestamp"] - window)
        for e in taken
        if e.get("hitPoints") is not None and e["hitPoints"] < low_limit
    ]
    starts: list[float] = []
    group: list[float] = []
    for start in sorted(candidates):
        # Mesmo incidente enquanto cai no trecho que o pico já analisa (janela + cura depois).
        if group and start - group[-1] > window + cfg["heal_window_s"] * 1000:
            starts.append(max(group, key=window_damage))
            group = []
        group.append(start)
    if group:
        starts.append(max(group, key=window_damage))
    return starts


def damage_peaks(
    fight: dict[str, Any], rules: dict[str, Any], encounter: dict[str, Any] | None
) -> list[DamagePeak]:
    top = max_hp(fight)
    if not top:
        return []
    cfg = peak_settings(encounter)
    classes = mechanic_classes(encounter)
    english = wcl_ability_names(fight)
    taken = _taken(fight)
    series = _hp_series(fight, top)
    spans = phase_spans(fight)
    window = cfg["window_s"] * 1000
    after = cfg["heal_window_s"] * 1000
    defensives = _available_defensives(fight, rules)
    active_windows = {
        spell_name(d["ability_id"], d["name"]): buff_windows(fight, d["buff_id"])
        for d in rules["defensives"]
    }
    heals = fight["events"].get("healing_taken") or []

    peaks = []
    for start in _peak_starts(taken, top, cfg):
        end = start + window
        hits = [e for e in taken if start <= e["timestamp"] < end]
        total = sum(_amount(e) for e in hits)
        by_ability: dict[int, float] = {}
        for e in hits:
            by_ability[e["abilityGameID"]] = by_ability.get(e["abilityGameID"], 0.0) + _amount(e)
        mechanics = tuple(
            MechanicShare(
                ability_id=a,
                name=spell_name(a, english.get(a)),
                mechanic_class=classes.get(a, "unknown"),
                damage=d,
                share=d / total if total else 0.0,
            )
            for a, d in sorted(by_ability.items(), key=lambda x: -x[1])
        )
        hp_values = [hp for t, hp in series if start <= t <= end]
        min_hp = min(hp_values, default=top)
        active = next(
            (
                name
                for name, ws in active_windows.items()
                if any(a <= end and b >= start for a, b in ws)
            ),
            None,
        )
        ready = tuple(
            spell_name(d["ability_id"], d["name"])
            for d in defensives
            if active is None and _ready(fight, d, start)
        )
        heal = sum(e.get("amount", 0) for e in heals if start <= e["timestamp"] <= end + after)
        heal_pct = 100 * heal / top
        low_s = _time_below(series, cfg["low_hp_pct"] / 100 * top, start, end + after)
        low_heal = low_s > cfg["low_hp_s"] and heal_pct < cfg["low_heal_pct_hp"]
        avoidable = sum(m.share for m in mechanics if m.mechanic_class == "avoidable")

        verdict: Verdict = "ok"
        if avoidable >= cfg["avoidable_share"]:
            verdict = "evitavel"
        elif active is None and ready and min_hp < cfg["danger_hp_pct"] / 100 * top:
            verdict = "defensivo"
        elif low_heal:
            verdict = "cura"

        span = phase_at(spans, start) or (spans[0] if spans else None)
        peaks.append(
            DamagePeak(
                time_s=max(0.0, fight_s(fight, start)),
                phase=span.name if span else "",
                damage=total,
                damage_pct_hp=100 * total / top,
                min_hp_pct=100 * min_hp / top,
                mechanics=mechanics,
                defensive_active=active,
                defensives_ready=ready,
                heal_pct_hp=heal_pct,
                low_hp_s=low_s,
                low_heal=low_heal,
                verdict=verdict,
            )
        )
    return peaks


def avoidable_pct_hp_per_min(fight: dict[str, Any], encounter: dict[str, Any] | None) -> float:
    """Dano de mecânicas evitáveis, em % da vida máxima por minuto (compara com os tops sem
    depender do equipamento)."""
    top = max_hp(fight)
    minutes = duration_s(fight) / 60
    if not top or not minutes:
        return 0.0
    classes = mechanic_classes(encounter)
    damage = sum(
        _amount(e) for e in _taken(fight) if classes.get(e["abilityGameID"]) == "avoidable"
    )
    return 100 * damage / top / minutes
