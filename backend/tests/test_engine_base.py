"""Base do motor: fases, referência dos tops, tabela por habilidade e dano por alvo."""

import gzip
import json
from functools import lru_cache
from pathlib import Path
from statistics import fmean

import pytest

from app.engine.abilities import ability_profile, ability_table
from app.engine.baseline import reference
from app.engine.fight import casts, phase_spans, total_damage
from app.engine.names import spell_name
from app.engine.targets import target_profile, target_table

FIXTURES = Path(__file__).parent / "fixtures" / "nekzali_mythic_326_328"
MISSILES_CAST, MISSILES_DAMAGE, BLAST, METEORITE = 5143, 7268, 30451, 449569
BOSS, AMANI = 259927, 261509


@lru_cache
def load(name: str) -> dict:
    return json.loads(gzip.decompress((FIXTURES / name).read_bytes()))


def tops() -> list[dict]:
    return [load(f"top{i:02d}.json.gz") for i in range(1, 11)]


def synthetic(
    transitions: list[tuple[int, int]],
    end: int,
    casts_: list[tuple[int, int]] = (),
    damage: list[tuple[int, int, int]] = (),
    actors: list[dict] | None = None,
) -> dict:
    """Luta mínima: transições (id, ms), casts (id, ms), dano (id, ms, valor)."""
    return {
        "meta": {
            "fight": {
                "startTime": 0,
                "endTime": end,
                "phaseTransitions": [{"id": i, "startTime": t} for i, t in transitions],
            }
        },
        "phases": [
            {"id": 1, "name": "Stage One", "isIntermission": False},
            {"id": 2, "name": "Intermission", "isIntermission": True},
        ],
        "actors": actors or [],
        "abilities": [],
        "events": {
            "casts": [
                {"type": "cast", "abilityGameID": a, "timestamp": t, "sourceID": 1}
                for a, t in casts_
            ],
            "buffs": [],
            "damage_done": [
                {"type": "damage", "abilityGameID": a, "timestamp": t, "amount": v, "targetID": 9}
                for a, t, v in damage
            ],
        },
    }


# --- Fases --------------------------------------------------------------------


def test_reference_kill_has_three_phases_with_portuguese_names():
    spans = phase_spans(load("reference_harmonist.json.gz"))
    assert [(s.id, s.name, s.intermission) for s in spans] == [
        (1, "Fase 1", False),
        (2, "Intermissão", True),
        (3, "Fase 2", False),
    ]
    assert spans[1].duration_s == pytest.approx(100.7, abs=0.1)


def test_fight_without_transitions_is_a_single_phase():
    fight = synthetic([], end=60_000)
    del fight["meta"]["fight"]["phaseTransitions"]
    assert [(s.id, s.start_ms, s.end_ms) for s in phase_spans(fight)] == [(1, 0, 60_000)]


def test_repeated_phase_adds_up_in_the_table():
    # Fase 1 (0–30 s), intermissão (30–40 s), Fase 1 de novo (40–70 s): 60 s de Fase 1.
    fight = synthetic(
        [(1, 0), (2, 30_000), (1, 40_000)],
        end=70_000,
        casts_=[(BLAST, t) for t in (1000, 2000, 45_000)],
        damage=[(BLAST, 1000, 100)],
    )
    phase = ability_profile(fight).phases[1]
    assert phase.duration_s == 60
    assert phase.casts[BLAST] == 3


def test_casts_skip_begincast_and_come_in_order():
    fight = synthetic([(1, 0)], end=10_000, casts_=[(BLAST, 5000), (BLAST, 1000)])
    fight["events"]["casts"].append({"type": "begincast", "abilityGameID": BLAST, "timestamp": 0})
    assert [c["timestamp"] for c in casts(fight, BLAST)] == [1000, 5000]


def test_damage_counts_absorbed():
    fight = synthetic([(1, 0)], end=10_000, damage=[(BLAST, 1000, 100)])
    fight["events"]["damage_done"][0]["absorbed"] = 50
    assert total_damage(fight) == 150


# --- Referência dos tops --------------------------------------------------------


def test_reference_lower_is_better():
    ref = reference([4, 5, 5, 6, 6, 6, 7, 8, 10, 11], better="lower")
    assert ref.median == 6
    assert ref.status(6) == "ok"
    assert ref.status(9) == "atencao"  # pior que 3 de cada 4 tops
    assert ref.status(12) == "erro"  # pior que o pior top
    assert ref.text(lambda v: f"{v:g}%") == "mediana dos 10 tops: 6%"


def test_reference_higher_is_better():
    ref = reference([97, 98, 98, 99, 99, 99, 99, 99.5, 99.5, 100], better="higher")
    assert ref.status(99) == "ok"
    assert ref.status(97.5) == "atencao"
    assert ref.status(96) == "erro"


def test_no_top_is_an_error_against_its_own_reference():
    values = [5.2, 9.3, 1.2, 8.0, 3.3, 6.7, 28.6, 16.8, 5.9, 6.8]
    ref = reference(values, better="lower")
    assert all(ref.status(v) != "erro" for v in values)


def test_few_tops_use_the_yaml_reserve():
    ref = reference([5, 6], better="lower", reserve={"warn": 8, "error": 12})
    assert not ref.from_tops
    assert (ref.status(7), ref.status(10), ref.status(13)) == ("ok", "atencao", "erro")
    assert "poucos tops" in ref.text(str)


def test_few_tops_without_reserve_is_a_bug():
    with pytest.raises(ValueError):
        reference([5], better="lower")


# --- Tabela por habilidade (RF22) ---------------------------------------------------


def test_t05_top_value_is_the_mean_of_the_tops():
    """T05: jogador × média dos top logs de exemplo."""
    profiles = [ability_profile(t) for t in tops()]
    table = ability_table(ability_profile(load("reference_harmonist.json.gz")), profiles)
    stage_two = next(t for t in table if t.phase_id == 3)
    missiles = next(line for line in stage_two.lines if line.key == MISSILES_CAST)

    expected = []
    for top in profiles:
        phase = top.phases[3]
        expected.append(100 * phase.damage[MISSILES_CAST] / phase.total_damage)
    assert missiles.top_dmg_pct == pytest.approx(fmean(expected))
    assert missiles.name == "Mísseis Arcanos"
    # Medido no kill de referência (28/10): 30,9% do dano no Harmonist, 35,3% nos tops; 35,5%
    # desde 04/11, sem o dano que o WCL credita ao Evocador que apoiou alguns tops (o Touch
    # deles vinha inflado pelo Ebon Might).
    assert missiles.player_dmg_pct == pytest.approx(30.9, abs=0.05)
    assert missiles.top_dmg_pct == pytest.approx(35.5, abs=0.05)


def test_cast_and_damage_ids_become_one_line():
    table = ability_table(ability_profile(load("reference_harmonist.json.gz")), [])
    keys = {line.key for t in table for line in t.lines}
    assert MISSILES_CAST in keys and MISSILES_DAMAGE not in keys
    meteorite = next(line for line in table[0].lines if line.key == METEORITE)
    assert meteorite.player_cpm is None  # sai do Barrage, sem cast próprio
    assert meteorite.top_cpm is None


def test_t14_phases_of_different_lengths_compare_by_rate():
    """T14: mesma rotação em fases de duração diferente dá a mesma taxa."""
    # Jogador: intermissão aos 30 s, 1 Blast a cada 3 s na Fase 1 (10 casts em 30 s).
    player = synthetic(
        [(1, 0), (2, 30_000)],
        end=60_000,
        casts_=[(BLAST, t) for t in range(0, 30_000, 3000)],
        damage=[(BLAST, 1000, 100)],
    )
    # Top: intermissão aos 60 s, o mesmo ritmo na Fase 1 (20 casts em 60 s).
    top = synthetic(
        [(1, 0), (2, 60_000)],
        end=90_000,
        casts_=[(BLAST, t) for t in range(0, 60_000, 3000)],
        damage=[(BLAST, 1000, 100)],
    )
    stage_one = ability_table(ability_profile(player), [ability_profile(top)])[0]
    blast = stage_one.lines[0]
    assert blast.player_cpm == pytest.approx(20)
    assert blast.top_cpm == pytest.approx(20)


def test_small_lines_stay_out():
    fight = synthetic([(1, 0)], end=60_000, damage=[(BLAST, 1000, 995), (METEORITE, 2000, 5)])
    keys = [line.key for line in ability_table(ability_profile(fight), [])[0].lines]
    assert keys == [BLAST]


def test_unknown_ability_keeps_the_english_name():
    assert spell_name(999_999, "Some New Spell") == "Some New Spell"


# --- Dano por alvo ---------------------------------------------------------------------


def test_targets_group_by_npc_and_put_the_boss_first():
    actors = [
        {"id": 9, "type": "NPC", "gameID": BOSS, "name": "Nek'zali the Soulcoiler"},
        {"id": 10, "type": "NPC", "gameID": AMANI, "name": "Restless Amani"},
        {"id": 11, "type": "NPC", "gameID": AMANI, "name": "Restless Amani"},
        {"id": 3, "type": "Player", "name": "raid_03"},
    ]
    fight = synthetic([(1, 0)], end=60_000, actors=actors)
    for target, value in ((9, 600), (10, 300), (11, 300), (3, 999)):
        fight["events"]["damage_done"].append(
            {
                "type": "damage",
                "abilityGameID": BLAST,
                "timestamp": 1000,
                "amount": value,
                "targetID": target,
            }
        )
    lines = target_table(target_profile(fight), [], boss_ids=frozenset({BOSS}))[0].lines
    assert [(line.name, line.boss, line.player_pct) for line in lines] == [
        ("Nek'zali, a Enrosca-almas", True, 50.0),  # dano em jogador não conta
        ("Amani Indócil", False, 50.0),
    ]


def test_reference_kill_targets_by_phase():
    player = target_profile(load("reference_harmonist.json.gz"))
    table = target_table(player, [target_profile(t) for t in tops()], frozenset({BOSS}))
    intermission = next(t for t in table if t.phase_id == 2)
    # Na intermissão o chefe não recebe dano: o alvo é o Eco de Jawae.
    assert intermission.lines[0].name == "Eco de Jawae"
    assert all(not line.boss for line in intermission.lines)
    for phase in table:
        assert sum(line.player_pct for line in phase.lines) == pytest.approx(100, abs=2)
