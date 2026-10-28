import gzip
import json
from pathlib import Path

import pytest

from app.engine.prismatic_bolt import bolt_procs, salvo_at_barrages

FIXTURES = Path(__file__).parent / "fixtures" / "nekzali_mythic_326_328"
BARRAGE, SALVO, PROC = 44425, 1242974, 1295942


def fight(casts: list[dict], buffs: list[dict], minutes: float = 1.0) -> dict:
    return {
        "meta": {"fight": {"startTime": 0, "endTime": minutes * 60_000}},
        "events": {"casts": casts, "buffs": buffs},
    }


def barrage(t: int) -> dict:
    return {"type": "cast", "abilityGameID": BARRAGE, "timestamp": t}


def salvo(t: int, kind: str, stack: int | None = None) -> dict:
    event = {"type": kind, "abilityGameID": SALVO, "timestamp": t}
    if stack is not None:
        event["stack"] = stack
    return event


def test_salvo_is_read_before_the_barrage_consumes_it():
    events = fight(
        casts=[barrage(1000), barrage(5000)],
        buffs=[
            salvo(100, "applybuff"),
            salvo(200, "applybuffstack", 12),
            salvo(1000, "removebuff"),  # o próprio Barrage consome no mesmo instante
            salvo(3000, "applybuff"),
            salvo(4000, "applybuffstack", 25),
        ],
    )

    assert salvo_at_barrages(events) == [12, 25]


def test_expected_procs_follow_two_percent_per_salvo():
    events = fight(
        casts=[barrage(1000), barrage(5000)],
        buffs=[
            salvo(200, "applybuffstack", 12),
            salvo(1000, "removebuff"),
            salvo(4000, "applybuffstack", 25),
            {"type": "applybuff", "abilityGameID": PROC, "timestamp": 5300},  # 0,3 s depois
            {"type": "applybuff", "abilityGameID": PROC, "timestamp": 9000},  # longe: não conta
        ],
    )

    procs = bolt_procs(events)

    assert procs.expected == pytest.approx(0.24 + 0.50)
    assert procs.received == 1
    assert procs.below_min_pct == 0
    assert procs.mean_salvo == pytest.approx(18.5)


@pytest.mark.skipif(not FIXTURES.exists(), reason="rode scripts/save_fixtures.py")
def test_reference_kill_was_unlucky_not_badly_played():
    # Kill de referência (28/10/2026): os acúmulos do Harmonist davam ~41 procs e vieram 28.
    reference = json.loads(gzip.decompress((FIXTURES / "reference_harmonist.json.gz").read_bytes()))

    procs = bolt_procs(reference)

    assert procs.barrages == 101
    assert procs.expected == pytest.approx(41.1, abs=0.1)
    assert procs.received == 28
    assert procs.luck_z == pytest.approx(-2.8, abs=0.1)
    assert procs.luck == "azar"
