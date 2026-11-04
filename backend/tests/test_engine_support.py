"""Desconto do crédito ao Evocador Aumentação (`engine/support.py`, decisão de 04/11): o
crédito por habilidade do WCL sai só dos golpes dados com Ebon Might, Prescience ou Shifting
Sands ativo; se não couber neles, sai de todos os golpes da habilidade por igual."""

import gzip
import json
from functools import lru_cache
from pathlib import Path

import pytest

from app.engine.fight import amount, damage_done, total_damage
from app.engine.support import support_windows

FIXTURES = Path(__file__).parent / "fixtures" / "nekzali_mythic_326_328"
EBON, PRESCIENCE = 395152, 410089
MISSILES, TOUCH = 7268, 210833
BUFFS = frozenset({EBON, PRESCIENCE, 413984})


@lru_cache
def load(name: str) -> dict:
    return json.loads(gzip.decompress((FIXTURES / name).read_bytes()))


def fight(buffs=(), damage=(), credited=None, end=100_000) -> dict:
    """Luta mínima: buffs (id, tipo, ms, fonte) e dano (id, ms, valor)."""
    return {
        "meta": {"fight": {"startTime": 0, "endTime": end}},
        "player": {"damage": None if credited is None else {"credited": credited}},
        "events": {
            "buffs": [
                {"abilityGameID": a, "type": k, "timestamp": t, "sourceID": s}
                for a, k, t, s in buffs
            ],
            "damage_done": [
                {"abilityGameID": a, "timestamp": t, "amount": v} for a, t, v in damage
            ],
        },
    }


@pytest.mark.parametrize(
    "name", ["reference_harmonist.json.gz"] + [f"top{i:02d}.json.gz" for i in range(1, 11)]
)
def test_damage_after_the_discount_is_the_official_total(name):
    """Nas 11 fixtures (top03 e top09 com Evocador), o dano do motor = total oficial do WCL."""
    data = load(name)
    assert total_damage(data) == pytest.approx(data["player"]["damage"]["total"], abs=1)


def test_supported_touch_matches_the_warcraft_logs():
    """O Touch do top03 vinha +46% pelos eventos; agora bate com o da tabela do WCL."""
    top03 = load("top03.json.gz")
    touch = sum(amount(e) for e in damage_done(top03) if e["abilityGameID"] == TOUCH)
    assert touch == pytest.approx(4_162_938, abs=1)


def test_only_supported_hits_lose_damage():
    data = fight(
        buffs=[(EBON, "applybuff", 10_000, 7), (EBON, "removebuff", 20_000, 7)],
        damage=[(MISSILES, 5_000, 100), (MISSILES, 15_000, 100), (MISSILES, 25_000, 100)],
        credited={str(MISSILES): 30},
    )
    assert [e["amount"] for e in damage_done(data)] == [100, 70, 100]


def test_credit_larger_than_the_supported_damage_comes_out_of_every_hit():
    data = fight(
        buffs=[(EBON, "applybuff", 10_000, 7), (EBON, "removebuff", 20_000, 7)],
        damage=[(TOUCH, 5_000, 100), (TOUCH, 15_000, 100)],
        credited={str(TOUCH): 150},
    )
    assert [e["amount"] for e in damage_done(data)] == [25, 25]


def test_credit_with_no_supported_hit_comes_out_of_every_hit():
    data = fight(damage=[(TOUCH, 5_000, 100), (TOUCH, 15_000, 300)], credited={str(TOUCH): 40})
    assert [e["amount"] for e in damage_done(data)] == [90, 270]


def test_without_warcraft_logs_numbers_nothing_changes():
    data = fight(buffs=[(EBON, "applybuff", 0, 7)], damage=[(MISSILES, 5_000, 100)], credited=None)
    assert [e["amount"] for e in damage_done(data)] == [100]


def test_two_evokers_windows_do_not_cut_each_other():
    """Com dois Evocadores, o fim do Ebon Might de um não fecha a janela do outro."""
    data = fight(
        buffs=[
            (EBON, "applybuff", 10_000, 1),
            (EBON, "applybuff", 12_000, 2),
            (EBON, "removebuff", 15_000, 1),
            (EBON, "removebuff", 30_000, 2),
            (PRESCIENCE, "applybuff", 29_000, 1),
            (PRESCIENCE, "removebuff", 40_000, 1),
        ]
    )
    assert support_windows(data, BUFFS) == [(10_000, 40_000)]


def test_buff_active_on_pull_and_until_the_end():
    data = fight(
        buffs=[(EBON, "removebuff", 5_000, 1), (EBON, "applybuff", 90_000, 1)], end=100_000
    )
    assert support_windows(data, BUFFS) == [(0, 5_000), (90_000, 100_000)]


def test_refresh_as_first_event_means_active_on_pull_and_does_not_close_a_window():
    data = fight(
        buffs=[
            (EBON, "refreshbuff", 3_000, 1),
            (EBON, "removebuff", 5_000, 1),
            (EBON, "applybuff", 10_000, 1),
            (EBON, "refreshbuff", 12_000, 1),
            (EBON, "removebuff", 20_000, 1),
        ]
    )
    assert support_windows(data, BUFFS) == [(0, 5_000), (10_000, 20_000)]


def test_remove_and_apply_in_the_same_ms_keep_the_window_open():
    data = fight(
        buffs=[
            (EBON, "applybuff", 10_000, 1),
            (EBON, "applybuff", 20_000, 1),  # mesmo ms da saída, mas chega antes na lista
            (EBON, "removebuff", 20_000, 1),
            (EBON, "removebuff", 30_000, 1),
        ]
    )
    assert support_windows(data, BUFFS) == [(10_000, 30_000)]


def test_absorbed_is_scaled_with_the_amount():
    data = fight(
        buffs=[(EBON, "applybuff", 0, 7)],
        damage=[(MISSILES, 5_000, 0)],
        credited={str(MISSILES): 25},
    )
    data["events"]["damage_done"][0]["absorbed"] = 100
    event = damage_done(data)[0]
    assert (event["amount"], event["absorbed"]) == (0, 75)


def test_real_hit_outside_the_support_windows_keeps_its_raw_value():
    top03 = load("top03.json.gz")
    windows = support_windows(top03, BUFFS)
    raw = [e for e in top03["events"]["damage_done"] if e["abilityGameID"] == MISSILES]
    outside = [
        i for i, e in enumerate(raw) if not any(a <= e["timestamp"] <= b for a, b in windows)
    ]
    assert outside
    kept = [e for e in damage_done(top03) if e["abilityGameID"] == MISSILES]
    for i in outside:
        assert kept[i]["amount"] == raw[i]["amount"]
    assert any(kept[i]["amount"] < raw[i]["amount"] for i in range(len(raw)) if i not in outside)


def test_credited_by_ability_reads_grouped_lines_and_sums_repeated_ids():
    from app.wcl.fetch import _credited_by_ability

    report = {
        "own": {
            "data": {
                "entries": [
                    {"guid": 7268, "total": 100, "totalRDPSTaken": 10},
                    {
                        "guid": 448659,  # Arcane Phoenix (pet): os ids dos eventos nas subentradas
                        "composite": True,
                        "totalRDPSTaken": 7,
                        "subentries": [
                            {"guid": 456139, "totalRDPSTaken": 5},
                            {"guid": 450499, "totalRDPSTaken": 2},
                        ],
                    },
                    {"guid": 450499, "totalRDPSTaken": 1},
                    {"guid": 30451, "totalRDPSTaken": 0},
                ]
            }
        }
    }
    assert _credited_by_ability(report) == {"7268": 10, "456139": 5, "450499": 3}
    assert _credited_by_ability({"own": None}) == {}
    assert _credited_by_ability(None) == {}
