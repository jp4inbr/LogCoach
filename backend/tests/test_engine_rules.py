"""Regras do motor (checks.py): casos do item 10 (T03, T04, T11–T13) e o kill de referência."""

import gzip
import json
from functools import lru_cache
from pathlib import Path

import pytest

from app.engine.checks import gap, num, run_checks
from app.engine.context import deaths, external_buffs
from app.engine.cooldowns import cooldown_stats, surge_holds
from app.engine.defensives import overlap_hits
from app.engine.measures import measure
from app.engine.potion import potion_stats
from app.engine.prismatic_bolt import bolt_munch
from app.engine.rules import load_encounter_rules, load_spec_rules
from app.engine.uptime import active_time_pct

FIXTURES = Path(__file__).parent / "fixtures" / "nekzali_mythic_326_328"
RULES = load_spec_rules()
NEKZALI = load_encounter_rules(3470)
PID = 10
SURGE, TOUCH, BARRAGE, BLAST, POTION = 365350, 321507, 44425, 30451, 1236616
SURGE_BUFF, PI, TIME_WARP, BARRIER, BOLT_PROC = 365362, 10060, 80353, 235450, 1295942
POSSESSION, DEPTHS, RITE = 1292034, 1293214, 1288772
STAGE_TWO = [(1, 0), (3, 20)]  # Grasping Depths só vale na Fase 3 (Stage Two)


def fight(
    end_s: float = 60,
    casts: list[tuple[int, float]] = (),
    buffs: list[tuple[int, str, float]] = (),
    taken: list[tuple[int, float]] = (),
    transitions: list[tuple[int, float]] = ((1, 0),),
    death_s: list[float] = (),
) -> dict:
    """Luta sintética: tempos em segundos; casts instantâneos (sem begincast)."""
    ms = lambda s: int(s * 1000)  # noqa: E731
    return {
        "meta": {
            "fight": {
                "startTime": 0,
                "endTime": ms(end_s),
                "phaseTransitions": [{"id": i, "startTime": ms(t)} for i, t in transitions],
            }
        },
        "phases": [
            {"id": 1, "name": "Stage One", "isIntermission": False},
            {"id": 2, "name": "Intermission", "isIntermission": True},
            {"id": 3, "name": "Stage Two", "isIntermission": False},
        ],
        "actors": [],
        "abilities": [],
        "player": {"actor": {"id": PID}},
        "events": {
            "casts": [
                {"type": "cast", "abilityGameID": a, "timestamp": ms(t), "sourceID": PID}
                for a, t in casts
            ],
            "buffs": [
                {"type": k, "abilityGameID": a, "timestamp": ms(t), "targetID": PID}
                for a, k, t in buffs
            ],
            "damage_done": [],
            "damage_taken": [
                {"type": "damage", "abilityGameID": a, "timestamp": ms(t), "targetID": PID}
                for a, t in taken
            ],
            "deaths": [{"type": "death", "targetID": PID, "timestamp": ms(t)} for t in death_s],
        },
    }


def check(checks, check_id):
    return next(c for c in checks if c.id == check_id)


@lru_cache
def load(name: str) -> dict:
    return json.loads(gzip.decompress((FIXTURES / name).read_bytes()))


@lru_cache
def reference_checks():
    player = measure(load("reference_harmonist.json.gz"), RULES, NEKZALI)
    tops = [measure(load(f"top{i:02d}.json.gz"), RULES, NEKZALI) for i in range(1, 11)]
    checks = run_checks(player, tops, RULES, NEKZALI)
    return player, tops, checks


# --- T03 e T12: tempo ativo ------------------------------------------------------------


def test_active_time_comes_from_the_warcraft_logs_when_present():
    """Com o número do WCL (tabela de casts), ele vale no lugar da conta própria."""
    data = fight(casts=[(BARRAGE, t) for t in range(30)])
    data["player"]["active_time_ms"] = 57_000
    assert active_time_pct(data, RULES) == pytest.approx(95)


def test_t03_idle_time_is_measured():
    """T03: 1 cast por segundo, com 5 s parado numa luta de 60 s (~8%)."""
    times = [t for t in range(60) if not 20 <= t < 25]
    pct = active_time_pct(fight(casts=[(BARRAGE, t) for t in times]), RULES)
    assert pct == pytest.approx(100 * 55 / 60, abs=1)


def test_t03_idle_time_is_an_error_against_the_reserve():
    times = [t for t in range(60) if not 20 <= t < 25]
    player = measure(fight(casts=[(BARRAGE, t) for t in times]), RULES)
    active = check(run_checks(player, [], RULES), "active_time")
    assert active.status == "erro"  # ~92% contra a reserva (atenção abaixo de 98, erro de 96)
    assert "poucos tops" in active.reference


def test_t12_intermission_without_targets_is_not_idle_time():
    """T12: 20 s de intermissão sem casts. Se o encontro diz que não há alvo, não conta."""
    times = [t for t in range(60) if not 20 <= t < 40]
    data = fight(casts=[(BARRAGE, t) for t in times], transitions=[(1, 0), (2, 20), (3, 40)])
    no_targets = {"downtime_excluded_phases": [2]}
    assert active_time_pct(data, RULES, no_targets) == pytest.approx(100, abs=1)
    # No Nek'zali a intermissão tem alvo (Eco de Jawae): ficar parado nela é tempo parado.
    assert active_time_pct(data, RULES, NEKZALI) == pytest.approx(100 * 40 / 60, abs=1)


def test_dead_time_is_not_idle_time():
    times = [t for t in range(30)]
    data = fight(end_s=60, casts=[(BARRAGE, t) for t in times], death_s=[30])
    assert deaths(data)[0].dead_s == pytest.approx(30)
    assert active_time_pct(data, RULES) == pytest.approx(100, abs=1)


def test_other_players_deaths_are_ignored():
    data = fight(death_s=[10])
    data["events"]["deaths"][0]["targetID"] = 99
    assert deaths(data) == []


# --- T04: usos de cooldown ------------------------------------------------------------------


def test_t04_cooldown_used_less_than_possible():
    """T04: Touch (CD 45 s) numa luta de 100 s: cabem 3 (0, 45, 90); usado 2 vezes."""
    data = fight(end_s=100, casts=[(TOUCH, 0), (TOUCH, 60)])
    stats = cooldown_stats(data, TOUCH, 45)
    assert (len(stats.uses), stats.possible, stats.missed) == (2, 3, 1)
    assert stats.uses[1].drift_s == pytest.approx(15)
    touch = check(run_checks(measure(data, RULES), [], RULES), "touch_uses")
    assert touch.status == "atencao"
    assert touch.player_value == "2 de 3 possíveis"


# --- T11: Surge segurado para casar com algo ---------------------------------------------


def test_t11_surge_held_for_the_boss_phase_is_aligned():
    """T11: Surge segurado 20 s, usado 3 s depois do início do Stage Two: casou com a fase."""
    data = fight(end_s=200, casts=[(SURGE, 0), (SURGE, 110)], transitions=[(1, 0), (3, 107)])
    surge = cooldown_stats(data, SURGE, 90)
    holds = surge_holds(data, surge, RULES, NEKZALI)
    assert len(holds) == 1 and holds[0].held_s == pytest.approx(20)
    assert holds[0].coincides == ("início da Fase 2",)
    assert check(
        run_checks(measure(data, RULES, NEKZALI), [], RULES, NEKZALI), "surge_hold"
    ).status == ("atencao")


def test_surge_held_for_nothing_is_an_error():
    data = fight(end_s=200, casts=[(SURGE, 0), (SURGE, 110)])
    hold = check(run_checks(measure(data, RULES, NEKZALI), [], RULES, NEKZALI), "surge_hold")
    assert hold.status == "erro"
    assert "nada que casasse" in hold.details[0]


def test_short_hold_is_not_listed():
    data = fight(end_s=200, casts=[(SURGE, 0), (SURGE, 98)])
    assert surge_holds(data, cooldown_stats(data, SURGE, 90), RULES, NEKZALI) == []


# --- T13: defensivo nos overlaps --------------------------------------------------------------


def test_t13_overlap_without_defensive_is_attention():
    """T13: Possession Barrage + Grasping Depths em 2 s, sem defensivo."""
    data = fight(taken=[(POSSESSION, 30), (DEPTHS, 32)], transitions=STAGE_TWO)
    hits = overlap_hits(data, RULES, NEKZALI)
    assert [(h.time_s, h.defended) for h in hits] == [(30, False)]
    defensive = check(
        run_checks(measure(data, RULES, NEKZALI), [], RULES, NEKZALI), "overlap_defensive"
    )
    assert defensive.status == "atencao"
    assert defensive.impact_pct is None  # risco, não perda de dano


def test_overlap_with_barrier_is_covered():
    data = fight(
        taken=[(POSSESSION, 30), (DEPTHS, 32)],
        buffs=[(BARRIER, "applybuff", 28), (BARRIER, "removebuff", 40)],
        transitions=STAGE_TWO,
    )
    assert overlap_hits(data, RULES, NEKZALI)[0].defended is True


def test_barrier_active_since_the_pull_covers_the_overlap():
    """Barreira posta antes do pull: só a saída aparece na luta."""
    data = fight(
        taken=[(POSSESSION, 30), (DEPTHS, 32)],
        buffs=[(BARRIER, "removebuff", 40)],
        transitions=STAGE_TWO,
    )
    assert overlap_hits(data, RULES, NEKZALI)[0].defended is True


def test_overlap_outside_its_phase_is_ignored():
    """O overlap do Stage Two (Fase 3) não vale na Fase 1."""
    data = fight(taken=[(POSSESSION, 30), (DEPTHS, 32)])
    assert overlap_hits(data, RULES, NEKZALI) == []


def test_two_overlaps_on_the_same_peak_count_once():
    """Possession Barrage com o DoT e o Grasping Depths juntos: um pico só (os dois overlaps
    postos na mesma fase para o teste)."""
    data = fight(taken=[(POSSESSION, 30), (DEPTHS, 31), (RITE, 31)], transitions=[(3, 0)])
    same_phase = {**NEKZALI, "overlaps": [{**o, "phase": 3} for o in NEKZALI["overlaps"]]}
    assert [h.time_s for h in overlap_hits(data, RULES, same_phase)] == [30]


def test_isolated_mechanic_needs_no_defensive():
    data = fight(taken=[(POSSESSION, 30), (DEPTHS, 50)])
    assert overlap_hits(data, RULES, NEKZALI) == []


# --- Poção, PI e munch -------------------------------------------------------------------------


def test_first_potion_goes_with_the_first_lust():
    # Lust aos 280 s (tarde): poção junto dele, sem poção no pull. Luta de 390 s: não cabe outra.
    data = fight(
        end_s=390,
        casts=[(SURGE, 0), (POTION, 282)],
        buffs=[(TIME_WARP, "applybuff", 280), (TIME_WARP, "removebuff", 320)],
    )
    stats = potion_stats(data, RULES)
    assert [(u.time_s, u.with_) for u in stats.uses] == [(282, "lust")]
    assert (stats.expected, stats.missing, stats.misaligned) == (1, 0, 0)


def test_second_potion_away_from_surge_is_misaligned():
    data = fight(
        end_s=420,
        casts=[(SURGE, 0), (SURGE, 90), (POTION, 2), (POTION, 320)],
        buffs=[(TIME_WARP, "applybuff", 0), (TIME_WARP, "removebuff", 40)],
    )
    stats = potion_stats(data, RULES)
    assert [u.with_ for u in stats.uses] == ["lust", None]
    assert stats.misaligned == 1


def test_potion_taken_before_the_pull_counts():
    """Poção antes do pull (top09): o cast fica fora da luta, só a saída do buff aparece."""
    data = fight(
        end_s=420,
        casts=[(SURGE, 0), (SURGE, 300), (POTION, 300)],
        buffs=[
            (POTION, "removebuff", 28),
            (POTION, "applybuff", 300),
            (POTION, "removebuff", 330),
            (TIME_WARP, "applybuff", 1),
            (TIME_WARP, "removebuff", 41),
        ],
    )
    stats = potion_stats(data, RULES)
    assert [(u.time_s, u.with_) for u in stats.uses] == [(-2, "lust"), (300, "Surto Arcano")]
    assert (stats.expected, stats.missing, stats.misaligned) == (2, 0, 0)


def test_potion_bonus_uses_the_player_intellect():
    data = fight()
    assert potion_stats(data, RULES).damage_bonus == RULES["consumables"][0]["damage_bonus"]
    data["player"]["combatant"] = {"stats": {"intellect": 3475}, "auras": []}
    assert potion_stats(data, RULES).damage_bonus == pytest.approx(695 / 3475)
    # Entrou com a poção ativa: o intelecto do pull já tem os 695 dela.
    data["player"]["combatant"]["auras"] = [{"ability": POTION, "stacks": 1}]
    data["player"]["combatant"]["stats"]["intellect"] = 3475 + 695
    assert potion_stats(data, RULES).damage_bonus == pytest.approx(695 / 3475)


def test_power_infusion_right_before_surge_counts_with_surge():
    data = fight(
        buffs=[
            (PI, "applybuff", 8),
            (PI, "removebuff", 23),
            (SURGE_BUFF, "applybuff", 10),
            (SURGE_BUFF, "removebuff", 27),
        ]
    )
    assert [(b.time_s, b.with_surge) for b in external_buffs(data, RULES)] == [(8, True)]


def test_munch_is_a_refresh_of_the_bolt_proc():
    data = fight(
        buffs=[
            (BOLT_PROC, "applybuff", 1),
            (BOLT_PROC, "refreshbuff", 2),
            (BOLT_PROC, "removebuff", 3),
            (BOLT_PROC, "applybuff", 5),
        ]
    )
    munch = bolt_munch(data, RULES)
    assert (munch.procs, munch.munched) == (3, 1)


# --- Kill de referência ---------------------------------------------------------------------------


def test_reference_kill_rules():
    _, _, checks = reference_checks()
    status = {c.id: c.status for c in checks}
    assert status["soul_entry"] == "erro"  # entradas com 0 e 1 de Salvo
    assert status["barrage_low_salvo"] == "atencao"  # 14,9% × mediana dos tops 6,8%
    assert status["surge_blasts"] == "atencao"  # 2,8 por janela × 0,0
    assert status["surge_touch_combo"] == "atencao"  # 4 de 5
    assert status["potion"] == "ok"  # 1ª com o Time Warp, 2ª com o Surto
    assert check(checks, "power_infusion").player_value == "2 (1 com o Surto)"
    assert check(checks, "barrage_low_salvo").reference == "mediana dos 10 tops: 6,8%"


def test_reference_kill_impacts_and_gap():
    """Números medidos em 03/11: Soul ~2,7%, Blast ~2,5%, sorte ~9,5%, diferença ~20%."""
    player, tops, checks = reference_checks()
    assert check(checks, "soul_entry").impact_pct == pytest.approx(2.7, abs=0.2)
    assert check(checks, "surge_blasts").impact_pct == pytest.approx(2.5, abs=0.2)
    assert check(checks, "barrage_low_salvo").impact_pct is None  # snowball: sem conta
    parts = gap(player, tops, checks)
    assert parts.total_pct == pytest.approx(20.0, abs=0.5)
    assert parts.luck_pct == pytest.approx(9.5, abs=0.5)
    assert parts.total_pct == pytest.approx(
        parts.mistakes_pct + parts.luck_pct + parts.unexplained_pct
    )


def test_tops_are_never_errors_against_a_reference_that_includes_them():
    _, tops, _ = reference_checks()
    for top in tops:
        checks = run_checks(top, tops, RULES, NEKZALI)
        compared = {"touch_drift", "barrage_low_salvo", "surge_blasts", "bolt_munch", "active_time"}
        assert all(c.status != "erro" for c in checks if c.id in compared)


def test_number_format_is_portuguese():
    assert num(1234.5) == "1.234,5"
    assert num(2.75, 2) == "2,75"
