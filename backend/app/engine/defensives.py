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
golpe e outro, a cura recebida (só `heal`; escudo absorvido já sai do dano) soma à vida, até a
vida máxima daquele momento. Sem a vida no log (fixture antiga), não há picos.
"""

import statistics
from dataclasses import dataclass
from typing import Any, Literal

from app.engine.context import deaths
from app.engine.fight import duration_s, fight_s, phase_at, phase_spans, start_ms
from app.engine.names import spell_name, wcl_ability_names
from app.engine.timeline import buff_windows, initial_stacks

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
    time_s: float  # início da janela mostrada, em segundos da luta
    phase: str
    damage: float
    damage_pct_hp: float  # dano da janela em % da vida máxima (contando escudos)
    min_hp_pct: float  # vida mínima do incidente
    mechanics: tuple[MechanicShare, ...]
    defensive_active: str | None  # já ativo quando a vida chegou ao mínimo
    defensive_late: str | None  # usado só depois da queda (até `heal_window_s`)
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
    """Vida máxima típica (mediana): base dos limites para achar candidatos e da régua de dano
    evitável. As porcentagens de cada pico usam a vida máxima daquele momento."""
    values = [
        e["maxHitPoints"]
        for e in fight["events"].get("damage_taken") or []
        if e.get("maxHitPoints")
    ]
    return statistics.median(values) if values else None


def _heals(fight: dict[str, Any]) -> list[dict[str, Any]]:
    """Só cura de verdade: `absorbed` (escudo que segurou um golpe) já sai do dano recebido, e
    contá-lo de novo como cura inflava a vida (revisão de 03/11)."""
    return [e for e in fight["events"].get("healing_taken") or [] if e.get("type") == "heal"]


def _hp_series(fight: dict[str, Any], top: float) -> list[tuple[float, float, float]]:
    """(instante, vida, vida máxima) depois de cada golpe (o valor do log) e de cada cura
    (soma até a vida máxima daquele momento, que muda com buffs de vida)."""
    events = sorted(
        [(e["timestamp"], 0, e) for e in fight["events"].get("damage_taken") or []]
        + [(e["timestamp"], 1, e) for e in _heals(fight)],
        key=lambda x: (x[0], x[1]),
    )
    series, hp, cap = [], top, top
    for t, kind, e in events:
        if kind == 0:
            if e.get("hitPoints") is None:
                continue
            hp, cap = e["hitPoints"], e.get("maxHitPoints") or cap
        else:
            hp = min(cap, hp + e.get("amount", 0))
        series.append((t, hp, cap))
    return series


def _time_below(series: list[tuple[float, float, float]], pct: float, a: float, b: float) -> float:
    """Segundos em [a, b] com a vida abaixo de `pct`% da máxima (a vida vale até a mudança
    seguinte)."""
    total, low, previous = 0.0, False, a
    for t, hp, cap in series:
        if t <= a:
            low = hp < pct / 100 * cap
            continue
        if t >= b:
            break
        if low:
            total += t - previous
        previous, low = t, hp < pct / 100 * cap
    if low:
        total += b - previous
    return total / 1000


def _available_defensives(fight: dict[str, Any], rules: dict[str, Any]) -> list[dict[str, Any]]:
    """Defensivos que o jogador tem: os de todo Arcano e os que ele usou na luta (talento)."""
    used = {e["abilityGameID"] for e in fight["events"]["casts"] if e["type"] == "cast"}
    return [d for d in rules["defensives"] if d.get("baseline") or d["ability_id"] in used]


def _casts_of(fight: dict[str, Any], ability_id: int) -> list[float]:
    return sorted(
        e["timestamp"]
        for e in fight["events"]["casts"]
        if e["type"] == "cast" and e["abilityGameID"] == ability_id
    )


def _ready(fight: dict[str, Any], defensive: dict[str, Any], at: float) -> bool:
    last = max((t for t in _casts_of(fight, defensive["ability_id"]) if t <= at), default=None)
    if last is None and initial_stacks(fight, defensive["buff_id"]):
        last = start_ms(fight)  # usado antes do pull: a recarga corre desde o começo
    return last is None or at - last >= defensive.get("cooldown_s", 0) * 1000


def _groups(taken: list[dict], top: float, cfg: dict[str, float]) -> list[tuple[float, float]]:
    """Trechos (início, fim) de cada incidente. Candidato = início de uma janela de
    `window_s` com `damage_pct_hp`% de dano, ou o primeiro golpe dos `window_s` que levaram a
    vida abaixo de `low_hp_pct`%. Candidatos a até `window_s + heal_window_s` do PRIMEIRO do
    grupo são o mesmo incidente (contar a partir do último encadeava dano contínuo em grupos de
    quase um minuto, escondendo quedas de vida; revisão de 03/11)."""
    window = cfg["window_s"] * 1000
    reach = window + cfg["heal_window_s"] * 1000
    damage_limit = cfg["damage_pct_hp"] / 100 * top
    times = [e["timestamp"] for e in taken]

    def window_damage(start: float) -> float:
        return sum(_amount(e) for e in taken if start <= e["timestamp"] < start + window)

    candidates = [t for t in times if window_damage(t) >= damage_limit]
    candidates += [
        next(t for t in times if t > e["timestamp"] - window)
        for e in taken
        if e.get("hitPoints") is not None
        and e.get("maxHitPoints")
        and e["hitPoints"] < cfg["low_hp_pct"] / 100 * e["maxHitPoints"]
    ]
    groups: list[tuple[float, float]] = []
    first = last = None
    for start in sorted(candidates):
        if first is not None and start - first > reach:
            groups.append((first, last + window))
            first = None
        if first is None:
            first = start
        last = start
    if first is not None:
        groups.append((first, last + window))
    return groups


def damage_peaks(
    fight: dict[str, Any], rules: dict[str, Any], encounter: dict[str, Any] | None
) -> list[DamagePeak]:
    """Um pico por incidente. Se a vida caiu abaixo de `danger_hp_pct`%, o pico mostra os
    `window_s` que levaram à vida mínima do incidente; senão, a janela com mais dano."""
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
    windows_by_defensive = [
        (d, spell_name(d["ability_id"], d["name"]), buff_windows(fight, d["buff_id"]))
        for d in rules["defensives"]
    ]
    heals = _heals(fight)

    def window_damage(start: float) -> float:
        return sum(_amount(e) for e in taken if start <= e["timestamp"] < start + window)

    peaks: list[DamagePeak] = []
    last_end = None
    for g_start, g_end in _groups(taken, top, cfg):
        in_group = [x for x in series if g_start <= x[0] <= g_end]
        lowest = min(in_group, key=lambda x: x[1] / x[2], default=None)
        if lowest is not None and lowest[1] < cfg["danger_hp_pct"] / 100 * lowest[2]:
            w_start = next(e["timestamp"] for e in taken if e["timestamp"] > lowest[0] - window)
        else:
            starts = [e["timestamp"] for e in taken if g_start <= e["timestamp"] <= g_end]
            w_start = max(starts or [g_start], key=window_damage)
        w_end = w_start + window
        in_window = [x for x in series if w_start <= x[0] <= max(w_end, w_start)]
        t_ref, hp_ref, cap = min(
            in_window or [(w_start, top, top)], key=lambda x: (x[1] / x[2], x[0])
        )
        if lowest is not None and lowest[1] / lowest[2] < hp_ref / cap:
            t_ref, hp_ref, cap = lowest

        # Janela que começa antes do fim do pico anterior (fim da janela ou vida mínima) é o
        # mesmo incidente (grupos vizinhos podem cair na mesma queda): fica o de vida mais baixa.
        replace_last = False
        if peaks and last_end is not None and w_start < last_end:
            if 100 * hp_ref / cap >= peaks[-1].min_hp_pct:
                continue
            replace_last = True
        last_end = max(w_end, t_ref)

        hits = [e for e in taken if w_start <= e["timestamp"] <= max(w_end, t_ref)]
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
        # Ativo = já estava ativo quando a vida chegou ao mínimo; usado depois disso é reação.
        active = next(
            (name for _, name, ws in windows_by_defensive if any(a < t_ref <= b for a, b in ws)),
            None,
        )
        late = next(
            (
                name
                for d, name, _ in windows_by_defensive
                if active is None
                and any(t_ref < c <= t_ref + after for c in _casts_of(fight, d["ability_id"]))
            ),
            None,
        )
        ready = tuple(
            spell_name(d["ability_id"], d["name"])
            for d in defensives
            # Pronto até o instante da vida mínima: dava para usar antes do golpe que doeu.
            if active is None and _ready(fight, d, t_ref)
        )
        heal = sum(e.get("amount", 0) for e in heals if w_start <= e["timestamp"] <= t_ref + after)
        heal_pct = 100 * heal / cap
        low_s = _time_below(series, cfg["low_hp_pct"], g_start, g_end + after)
        low_heal = low_s > cfg["low_hp_s"] and heal_pct < cfg["low_heal_pct_hp"]
        min_pct = 100 * hp_ref / cap
        avoidable = sum(m.share for m in mechanics if m.mechanic_class == "avoidable")

        verdict: Verdict = "ok"
        if avoidable >= cfg["avoidable_share"]:
            verdict = "evitavel"
        elif active is None and ready and min_pct < cfg["danger_hp_pct"]:
            verdict = "defensivo"
        elif low_heal:
            verdict = "cura"

        span = phase_at(spans, w_start) or (spans[0] if spans else None)
        if replace_last:
            peaks.pop()
        peaks.append(
            DamagePeak(
                time_s=max(0.0, fight_s(fight, w_start)),
                phase=span.name if span else "",
                damage=total,
                damage_pct_hp=100 * total / cap,
                min_hp_pct=min_pct,
                mechanics=mechanics,
                defensive_active=active,
                defensive_late=late,
                defensives_ready=ready,
                heal_pct_hp=heal_pct,
                low_hp_s=low_s,
                low_heal=low_heal,
                verdict=verdict,
            )
        )
    return peaks


def avoidable_pct_hp_per_min(fight: dict[str, Any], encounter: dict[str, Any] | None) -> float:
    """Dano de mecânicas evitáveis, em % da vida máxima por minuto vivo (compara com os tops sem
    depender do equipamento)."""
    top = max_hp(fight)
    minutes = (duration_s(fight) - sum(d.dead_s for d in deaths(fight))) / 60
    if not top or minutes <= 0:
        return 0.0
    classes = mechanic_classes(encounter)
    damage = sum(
        _amount(e) for e in _taken(fight) if classes.get(e["abilityGameID"]) == "avoidable"
    )
    return 100 * damage / top / minutes
