"""As regras do Mago Arcano: cada uma vira um `Check` com status, régua e impacto.

Escopo fechado com o Arthur em 03/11 (CLAUDE.md, "Decisões já tomadas"):
- limites de desempenho saem dos tops (`baseline.reference`), com a referência à vista;
- limites que são mecânica do jogo ou regra do Arthur ficam no YAML;
- `impact_pct` em % do dano do próprio jogador, só onde há conta defensável;
- a diferença para os tops = erros + sorte do Prismatic Bolt + não explicado (`gap`).
"""

from dataclasses import dataclass, field, replace
from statistics import fmean, median
from typing import Any

from app.engine.baseline import Reference, reference
from app.engine.measures import FightMeasures
from app.engine.names import spell_name
from app.schemas import Status

STATUS_ORDER = {"ok": 0, "atencao": 1, "erro": 2}


@dataclass(frozen=True)
class Check:
    id: str
    name: str
    status: Status
    player_value: str
    top_value: str
    reference: str | None = None  # de onde saiu o limite ("mediana dos 10 tops: 6%")
    impact_pct: float | None = None  # % do dano do jogador; None = sem conta (ou risco)
    note: str | None = None
    details: tuple[str, ...] = field(default_factory=tuple)  # fatos para o texto e para a IA


@dataclass(frozen=True)
class Gap:
    """Quanto dano a mais os tops fizeram, em % do dano do jogador, e de onde veio."""

    total_pct: float
    mistakes_pct: float  # soma dos impactos das regras
    luck_pct: float  # procs de Prismatic Bolt abaixo do esperado (negativo = teve sorte)
    unexplained_pct: float  # o resto (RF23)


# --- Formatação em português ------------------------------------------------------


def num(value: float, decimals: int = 1) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(value: float, decimals: int = 1) -> str:
    return f"{num(value, decimals)}%"


def secs(value: float, decimals: int = 1) -> str:
    return f"{num(value, decimals)} s"


def clock(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def _share(part: float, damage: float) -> float:
    return 100 * part / damage if damage else 0.0


def _cap(status: Status, limit: Status) -> Status:
    return status if STATUS_ORDER[status] <= STATUS_ORDER[limit] else limit


# --- Regras -----------------------------------------------------------------------


def _combo(p: FightMeasures, tops: list[FightMeasures], rules: dict[str, Any]) -> Check:
    gap = rules["combos"][0]["max_gap_s"]
    aligned = [c for c in p.combos if c.aligned]
    top_total = sum(len(t.combos) for t in tops)
    top_aligned = sum(c.aligned for t in tops for c in t.combos)

    # Custo: o Touch que ficou fora do Surge rende menos que um Touch casado.
    paired = {c.touch_s for c in aligned}
    aligned_damage = [d for t, d in p.touch_damage if t in paired]
    loss = 0.0
    details = []
    for combo in p.combos:
        if combo.aligned:
            continue
        nxt = next(((t, d) for t, d in p.touch_damage if t > combo.surge_s), None)
        if nxt is not None and aligned_damage:
            loss += max(0.0, fmean(aligned_damage) - nxt[1])
            details.append(
                f"Surto aos {clock(combo.surge_s)}: Toque só {secs(nxt[0] - combo.surge_s)} depois"
            )
        else:
            details.append(f"Surto aos {clock(combo.surge_s)} sem Toque logo depois")
    missed = len(p.combos) - len(aligned)
    return Check(
        id="surge_touch_combo",
        name=f"{spell_name(365350)} → {spell_name(321507)} em até {secs(gap)}",
        status="ok" if missed == 0 else "atencao",
        player_value=f"{len(aligned)} de {len(p.combos)}",
        top_value=pct(100 * top_aligned / top_total, 0) if top_total else "—",
        impact_pct=_share(loss, p.damage) if loss else None,
        details=tuple(details),
    )


def _uses(
    check_id: str,
    ability_id: int,
    player: int,
    possible: int,
    top_missed: list[int],
    cost_each: float,
    damage: float,
) -> Check:
    missed = max(0, possible - player)
    usual = median(top_missed) if top_missed else 0
    status: Status = "atencao" if missed > usual else "ok"
    return Check(
        id=check_id,
        name=f"Usos de {spell_name(ability_id)}",
        status=status,
        player_value=f"{player} de {possible} possíveis",
        top_value=f"tops deixam de usar {num(usual, 1)} em média" if top_missed else "—",
        impact_pct=_share((missed - usual) * cost_each, damage) if status != "ok" else None,
        note="Possível = usar no CD desde o pull até o fim da luta.",
    )


def _touch_drift(p: FightMeasures, tops: list[FightMeasures], rules: dict[str, Any]) -> Check:
    ref = reference(
        [t.touch.mean_drift_s for t in tops], "lower", rules["reserve"]["touch_drift_s"]
    )
    return _ref_check(
        "touch_drift",
        f"Atraso do {spell_name(321507)}",
        p.touch.mean_drift_s,
        ref,
        secs,
        note="Atraso médio em relação ao CD. Atrasar o Toque dessincroniza o próximo Surto.",
    )


def _surge_hold(p: FightMeasures, tops: list[FightMeasures], rules: dict[str, Any]) -> Check:
    limits = rules["surge_hold"]
    status: Status = "ok"
    details = []
    for hold in p.surge_holds:
        with_ = ", ".join(hold.coincides) if hold.coincides else "nada que casasse"
        details.append(f"Surto aos {clock(hold.time_s)}: segurado {secs(hold.held_s, 0)} ({with_})")
        level: Status = (
            "erro" if hold.held_s > limits["error_s"] and not hold.coincides else "atencao"
        )
        status = max(status, level, key=STATUS_ORDER.get)
    top_holds = sum(len(t.surge_holds) for t in tops)
    top_uses = sum(len(t.surge.uses) for t in tops)
    return Check(
        id="surge_hold",
        name=f"{spell_name(365350)} segurado mais de {secs(limits['warn_s'], 0)}",
        status=status,
        player_value=f"{len(p.surge_holds)} de {len(p.surge.uses)}",
        top_value=f"{top_holds} de {top_uses}" if tops else "—",
        note="Segurar para casar com poção, lust, Infusão de Poder ou fase do chefe pode valer.",
        details=tuple(details),
    )


def _ref_check(
    check_id: str,
    name: str,
    value: float,
    ref: Reference,
    fmt,
    impact_pct: float | None = None,
    note: str | None = None,
    details: tuple[str, ...] = (),
) -> Check:
    status = ref.status(value)
    return Check(
        id=check_id,
        name=name,
        status=status,
        player_value=fmt(value),
        top_value=fmt(ref.median) if ref.median is not None else "—",
        reference=ref.text(fmt),
        impact_pct=impact_pct if status != "ok" else None,
        note=note,
        details=details,
    )


def _barrage(p: FightMeasures, tops: list[FightMeasures], rules: dict[str, Any]) -> Check:
    barrage = rules["barrage"]
    ref = reference([t.barrage_low_pct for t in tops], "lower", barrage["pct_below_min_reserve"])
    return _ref_check(
        "barrage_low_salvo",
        f"{spell_name(44425)} com menos de {barrage['min_salvo']} acúmulos",
        p.barrage_low_pct,
        ref,
        pct,
        note="O ideal é nunca. O custo é o efeito bola de neve (Abstração, Meteoritos), "
        "que não dá para isolar em %.",
    )


def _soul(p: FightMeasures, tops: list[FightMeasures], rules: dict[str, Any]) -> Check:
    soul = rules["arcane_soul"]
    low = [e for e in p.soul if e.mistake]
    ideal = sum(not e.below_ideal for e in p.soul)
    top_low = sum(e.mistake for t in tops for e in t.soul)
    top_total = sum(len(t.soul) for t in tops)
    per_salvo = (
        p.cast.barrage_per_salvo + rules["prismatic_bolt_rng"]["proc_per_salvo"] * p.cast.bolt
    )
    details = [
        f"Entrada aos {clock(e.start_s)} com {e.salvo} de Salvo"
        + (" (Salva nos 2 últimos GCDs)" if e.barrage_in_last_gcds else "")
        for e in low
    ]
    return Check(
        id="soul_entry",
        name=f"Entradas na {spell_name(451038)} com menos de {soul['min_salvo']} de Salvo",
        status="erro" if low else "ok",
        player_value=f"{len(low)} de {len(p.soul)} ({', '.join(str(e.salvo) for e in p.soul)})",
        top_value=f"{top_low} de {top_total}" if tops else "—",
        impact_pct=_share(p.soul_missing_salvo * per_salvo, p.damage) if low else None,
        note=f"Ideal: {soul['ideal_salvo']} ou mais (você: {ideal} de {len(p.soul)}). "
        "Sem Salva nos 2 últimos GCDs antes da Alma.",
        details=tuple(details),
    )


def _empty_handed(p: FightMeasures, tops: list[FightMeasures]) -> Check:
    empty = [w for w in p.later_windows if w.empty_handed]
    top_empty = sum(w.empty_handed for t in tops for w in t.later_windows)
    top_total = sum(len(t.later_windows) for t in tops)
    return Check(
        id="surge_empty_handed",
        name=f"{spell_name(365350)} de mão vazia (menos de 12 de Salvo e sem Abstração)",
        status="atencao" if empty else "ok",
        player_value=f"{len(empty)} de {len(p.later_windows)}",
        top_value=f"{top_empty} de {top_total}" if tops else "—",
        note="O custo já aparece nos Impactos Arcanos dentro do Surto.",
        details=tuple(f"Surto aos {clock(w.start_s)}" for w in empty),
    )


def _blasts(p: FightMeasures, tops: list[FightMeasures], rules: dict[str, Any]) -> Check:
    ref = reference(
        [t.blasts_per_window for t in tops], "lower", rules["surge_window"]["blasts_reserve"]
    )
    usual = ref.median if ref.from_tops else ref.warn
    excess = max(0.0, p.blasts_per_window - usual) * len(p.later_windows)
    loss = excess * max(0.0, p.cast.missiles - p.cast.blast)
    check = _ref_check(
        "surge_blasts",
        f"{spell_name(30451)} dentro do {spell_name(365350)} (fora o de abertura)",
        p.blasts_per_window,
        ref,
        lambda v: f"{num(v)} por janela",
        impact_pct=_share(loss, p.damage) if loss else None,
        details=tuple(
            f"Surto aos {clock(w.start_s)}: {w.arcane_blasts} Impactos" for w in p.later_windows
        ),
    )
    # Pouca Abstração recebida (pior que 3 de cada 4 tops): pode ter sido azar, não passa
    # de atenção (regra do Arthur: "6 ou mais é erro, ou muito azar").
    if tops and check.status == "erro":
        cc = reference([t.clearcasting_per_min for t in tops], "higher", {"warn": 0, "error": 0})
        if cc.status(p.clearcasting_per_min) != "ok":
            return replace(
                check,
                status="atencao",
                note=f"Pouca Abstração recebida ({num(p.clearcasting_per_min)} por minuto; "
                f"{cc.text(num)}): pode ter sido azar.",
            )
    return check


def _bolt(p: FightMeasures, tops: list[FightMeasures], rules: dict[str, Any]) -> Check:
    """A decisão (procs esperados pelo Salvo) é a regra; a sorte vai para o `gap`."""
    minutes = p.duration_s / 60
    ref = reference(
        [t.bolt.expected_per_min for t in tops], "higher", rules["reserve"]["bolt_expected_per_min"]
    )
    luck = {"azar": "azar", "sorte": "sorte", "normal": "dentro do normal"}[p.bolt.luck]
    return _ref_check(
        "prismatic_bolt",
        f"{spell_name(1295924)}: procs esperados pelo Salvo (decisão)",
        p.bolt.expected_per_min,
        ref,
        lambda v: f"{num(v)} por minuto",
        note=(
            f"Recebidos {p.bolt.received} de ~{num(p.bolt.expected, 0)} esperados em "
            f"{num(minutes)} min ({luck}). A spec depende muito de sorte: azar não é erro."
        ),
    )


def _munch(p: FightMeasures, tops: list[FightMeasures], rules: dict[str, Any]) -> Check:
    ref = reference(
        [t.munch.pct for t in tops], "lower", rules["prismatic_bolt_rng"]["munch_reserve"]
    )
    usual = ref.median if ref.from_tops else ref.warn
    extra = max(0.0, p.munch.munched - usual / 100 * p.munch.procs)
    return _ref_check(
        "bolt_munch",
        f"{spell_name(1295924)} perdida por {spell_name(44425)} com proc ativo",
        p.munch.pct,
        ref,
        pct,
        impact_pct=_share(extra * p.cast.bolt, p.damage) if extra else None,
        note=f"{p.munch.munched} de {p.munch.procs} procs perdidos. Os tops também perdem alguns.",
    )


def _potion(p: FightMeasures, tops: list[FightMeasures], rules: dict[str, Any]) -> Check:
    potion = rules["consumables"][0]
    stats = p.potions
    rate_in, rate_out = p.surge_followup
    bonus, duration = stats.damage_bonus, potion["duration_s"]
    loss = stats.missing * bonus * rate_in * duration
    loss += stats.misaligned * bonus * max(0.0, rate_in - rate_out) * duration
    top_aligned = sum(u.aligned for t in tops for u in t.potions.uses)
    top_total = sum(t.potions.expected for t in tops)
    details = [
        f"Poção aos {clock(u.time_s)}: "
        + (f"junto do {u.with_}" if u.aligned else "fora do Surto e do lust")
        for u in stats.uses
    ]
    if stats.first_lust_s is not None:
        details.append(f"Primeiro lust aos {clock(stats.first_lust_s)}")
    return Check(
        id="potion",
        name="Poções junto do lust e do Surto",
        status="atencao" if stats.missing or stats.misaligned else "ok",
        player_value=f"{len(stats.uses) - stats.misaligned} de {stats.expected}",
        top_value=f"{top_aligned} de {top_total}" if tops else "—",
        impact_pct=_share(loss, p.damage) if loss else None,
        note="A 1ª vai junto do primeiro lust; segurar a 2ª para um Surto é o recomendado.",
        details=tuple(details),
    )


def _active(p: FightMeasures, tops: list[FightMeasures], rules: dict[str, Any]) -> Check:
    # Uma régua só para todos: a do WCL se o jogador e todos os tops a têm; senão a própria,
    # que dá 3 a 5 pontos a menos e não pode ser comparada com a do WCL.
    wcl = all(m.active_wcl_pct is not None for m in [p, *tops])
    value = p.active_wcl_pct if wcl else p.active_own_pct
    values = [t.active_wcl_pct if wcl else t.active_own_pct for t in tops]
    reserve = rules["reserve"]["active_time_pct" if wcl else "active_time_pct_own"]
    ref = reference(values, "higher", reserve)
    usual = ref.median if ref.from_tops else ref.warn
    impact = 100 * (usual / value - 1) if value and usual > value else None
    return _ref_check(
        "active_time",
        "Tempo ativo",
        value,
        ref,
        pct,
        impact_pct=impact,
        note="A intermissão não conta como tempo parado quando há alvo (troca de alvo).",
    )


def _defensive(p: FightMeasures, tops: list[FightMeasures]) -> Check:
    open_hits = [h for h in p.overlaps if not h.defended]
    top_defended = sum(h.defended for t in tops for h in t.overlaps)
    top_total = sum(len(t.overlaps) for t in tops)
    return Check(
        id="overlap_defensive",
        name="Defensivo nos picos de dano (overlaps)",
        status="atencao" if open_hits else "ok",
        player_value=f"{len(p.overlaps) - len(open_hits)} de {len(p.overlaps)}",
        top_value=f"{top_defended} de {top_total}" if tops else "—",
        note="Risco, não perda de dano."
        + (
            " Os tops também quase não usam."
            if top_total and top_defended / top_total < 0.25
            else ""
        ),
        details=tuple(f"{h.name} aos {clock(h.time_s)}" for h in open_hits),
    )


def _externals(p: FightMeasures, tops: list[FightMeasures]) -> Check:
    mine = [b for b in p.externals if b.name == "power_infusion"]
    with_surge = sum(b.with_surge for b in mine)
    per_top = [sum(b.name == "power_infusion" for b in t.externals) for t in tops]
    top_value = f"{num(fmean(per_top))} em média (o 1º: {per_top[0]})" if per_top else "—"
    return Check(
        id="power_infusion",
        name=f"{spell_name(10060)} recebida (buff de outro jogador)",
        status="ok",
        player_value=f"{len(mine)} ({with_surge} com o Surto)",
        top_value=top_value,
        note="Contexto, não erro.",
    )


def _deaths(p: FightMeasures) -> Check:
    dead = sum(d.dead_s for d in p.deaths)
    alive = p.duration_s - dead
    return Check(
        id="deaths",
        name="Mortes",
        status="erro" if p.deaths else "ok",
        player_value=str(len(p.deaths)),
        top_value="—",
        impact_pct=100 * dead / alive if p.deaths and alive > 0 else None,
        details=tuple(f"Morte aos {clock(d.time_s)} ({secs(d.dead_s, 0)} morto)" for d in p.deaths),
    )


def run_checks(
    player: FightMeasures,
    tops: list[FightMeasures],
    rules: dict[str, Any],
    encounter: dict[str, Any] | None = None,
) -> list[Check]:
    """Todas as regras, na ordem do relatório (a ordenação por impacto fica com quem monta)."""
    p = player
    checks = [
        _combo(p, tops, rules),
        _uses(
            "touch_uses",
            321507,
            len(p.touch.uses),
            p.touch.possible,
            [t.touch.missed for t in tops],
            p.cast.touch,
            p.damage,
        ),
        _touch_drift(p, tops, rules),
        _uses(
            "surge_uses",
            365350,
            len(p.surge.uses),
            p.surge.possible,
            [t.surge.missed for t in tops],
            p.surge_extra,
            p.damage,
        ),
        _surge_hold(p, tops, rules),
        _barrage(p, tops, rules),
        _soul(p, tops, rules),
        _empty_handed(p, tops),
        _blasts(p, tops, rules),
        _bolt(p, tops, rules),
        _munch(p, tops, rules),
        _potion(p, tops, rules),
        _active(p, tops, rules),
    ]
    if (encounter or {}).get("defensive_policy"):
        checks.append(_defensive(p, tops))
    checks += [_externals(p, tops), _deaths(p)]
    return checks


def gap(player: FightMeasures, tops: list[FightMeasures], checks: list[Check]) -> Gap:
    """Diferença para a média dos tops em % do dano do jogador, dividida em partes."""
    top_dps = fmean(t.dps for t in tops) if tops else player.dps
    total = 100 * (top_dps / player.dps - 1) if player.dps else 0.0
    mistakes = sum(c.impact_pct for c in checks if c.impact_pct)
    luck = _share((player.bolt.expected - player.bolt.received) * player.cast.bolt, player.damage)
    return Gap(total, mistakes, luck, total - mistakes - luck)
