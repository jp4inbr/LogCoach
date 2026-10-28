import gzip
import json
from pathlib import Path

import pytest

from app.engine.arcane_soul import soul_entries, surge_windows
from app.engine.prismatic_bolt import bolt_procs

FIXTURES = Path(__file__).parent / "fixtures" / "nekzali_mythic_326_328"
BARRAGE, MISSILES, SALVO, SOUL, OVERPOWERED = 44425, 5143, 1242974, 451038, 1277009


def cast(ability: int, t: int) -> dict:
    return {"type": "cast", "abilityGameID": ability, "timestamp": t}


def buff(ability: int, kind: str, t: int, stack: int | None = None) -> dict:
    event = {"type": kind, "abilityGameID": ability, "timestamp": t}
    if stack is not None:
        event["stack"] = stack
    return event


def fight(casts: list[dict], buffs: list[dict]) -> dict:
    return {
        "meta": {"fight": {"startTime": 0, "endTime": 60_000}},
        "events": {"casts": casts, "buffs": buffs},
    }


def test_barrage_right_before_soul_is_a_mistake():
    entry = soul_entries(
        fight(
            casts=[cast(MISSILES, 7000), cast(BARRAGE, 9000)],
            buffs=[
                buff(SALVO, "applybuffstack", 5000, 25),
                buff(SALVO, "removebuff", 9000),
                buff(SALVO, "applybuff", 9500),
                buff(SOUL, "applybuff", 10_000),
            ],
        )
    )[0]

    assert entry.salvo == 1
    assert entry.barrage_in_last_gcds is True
    assert entry.mistake is True


def test_overpowered_missiles_is_the_exception():
    entry = soul_entries(
        fight(
            casts=[cast(BARRAGE, 9000)],
            buffs=[
                buff(SALVO, "removebuff", 9000),
                buff(OVERPOWERED, "applybuff", 9800),
                buff(SALVO, "applybuffstack", 9800, 25),
                buff(SOUL, "applybuff", 10_000),
            ],
        )
    )[0]

    assert entry.salvo == 25
    assert entry.mistake is False


@pytest.fixture(scope="module")
def reference() -> dict:
    if not FIXTURES.exists():
        pytest.skip("rode scripts/save_fixtures.py")
    return json.loads(gzip.decompress((FIXTURES / "reference_harmonist.json.gz").read_bytes()))


def test_reference_soul_entries(reference):
    # Kill de referência (28/10/2026): entradas no Soul com Salvo baixo; tops entram com 24–25.
    entries = soul_entries(reference)

    assert [e.salvo for e in entries] == [0, 20, 1, 18, 22]
    assert entries[0].mistake is True


def test_reference_arcane_blast_inside_surge(reference):
    windows = surge_windows(reference)

    assert [w.arcane_blasts for w in windows] == [4, 4, 0, 4, 3]
    assert windows[0].opener is True


def test_reference_bolts_split_by_soul(reference):
    soul, outside, whole = (bolt_procs(reference, soul=s) for s in (True, False, None))

    assert soul.barrages + outside.barrages == whole.barrages
    assert soul.mean_salvo == pytest.approx(17.9, abs=0.1)
    assert outside.mean_salvo == pytest.approx(21.0, abs=0.1)
