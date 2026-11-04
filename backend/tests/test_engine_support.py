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
