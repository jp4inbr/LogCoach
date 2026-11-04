"""Picos de dano (T13): de onde veio, se um defensivo cabia ou se faltou cura."""

import gzip
import json
from functools import lru_cache
from pathlib import Path

import pytest

from app.engine.checks import run_checks
from app.engine.defensives import avoidable_pct_hp_per_min, damage_peaks
from app.engine.measures import measure
from app.engine.rules import load_encounter_rules, load_spec_rules

FIXTURES = Path(__file__).parent / "fixtures" / "nekzali_mythic_326_328"
RULES = load_spec_rules()
NEKZALI = load_encounter_rules(3470)
PID, HP = 10, 1000
BARRIER, ICE_BLOCK = 235450, 45438
POSSESSION, DEPTHS, RITE, CULTIST = 1292034, 1293214, 1288772, 1288554


def fight(
    hits: list[tuple[int, float, float, float]] = (),
    heals: list[tuple[float, float]] = (),
    casts: list[tuple[int, float]] = (),
    buffs: list[tuple[int, str, float]] = (),
    end_s: float = 60,
) -> dict:
    """Luta sintética: golpes (mecânica, segundo, dano, vida depois) numa vida de 1000."""
    ms = lambda s: int(s * 1000)  # noqa: E731
    return {
        "meta": {
            "fight": {
                "startTime": 0,
                "endTime": ms(end_s),
                "phaseTransitions": [{"id": 1, "startTime": 0}],
            }
        },
        "phases": [{"id": 1, "name": "Stage One", "isIntermission": False}],
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
                {
                    "type": "damage",
                    "abilityGameID": a,
                    "timestamp": ms(t),
                    "sourceID": 99,
                    "targetID": PID,
                    "amount": amount,
                    "hitPoints": hp,
                    "maxHitPoints": HP,
                }
                for a, t, amount, hp in hits
            ],
            "healing_taken": [
                {"type": "heal", "abilityGameID": 1, "timestamp": ms(t), "amount": amount}
                for t, amount in heals
            ],
            "deaths": [],
        },
    }


def test_small_hits_are_not_a_peak():
    data = fight(hits=[(RITE, 10, 200, 800), (RITE, 20, 200, 800)])
    assert damage_peaks(data, RULES, NEKZALI) == []


def test_t13_big_raid_hit_without_defensive_is_attention():
    """T13: 70% da vida em 2 s, vida a 30%, Barreira pronta e não usada."""
    data = fight(hits=[(POSSESSION, 30, 400, 600), (DEPTHS, 32, 300, 300)])
    [peak] = damage_peaks(data, RULES, NEKZALI)
    assert peak.time_s == 30
    assert peak.damage_pct_hp == pytest.approx(70)
    assert peak.min_hp_pct == pytest.approx(30)
    assert len(peak.defensives_ready) == 1  # a Barreira Prismática
    assert peak.verdict == "defensivo"
    checks = run_checks(measure(data, RULES, NEKZALI), [], RULES, NEKZALI)
    check = next(c for c in checks if c.id == "damage_peaks")
    assert check.status == "atencao"
    assert check.impact_pct is None  # risco, não perda de dano
    assert "defensivo cabia" in check.details[0]


def test_peak_healed_through_needs_no_defensive():
    """A cura segurou: a vida nunca caiu abaixo de 50%."""
    data = fight(
        hits=[(POSSESSION, 30, 400, 600), (DEPTHS, 32, 300, 700)],
        heals=[(31, 400)],
    )
    [peak] = damage_peaks(data, RULES, NEKZALI)
    assert peak.verdict == "ok"


def test_peak_with_barrier_active_is_covered():
    data = fight(
        hits=[(POSSESSION, 30, 400, 600), (DEPTHS, 32, 300, 300)],
        heals=[(33, 500)],
        buffs=[(BARRIER, "applybuff", 28), (BARRIER, "removebuff", 40)],
    )
    [peak] = damage_peaks(data, RULES, NEKZALI)
    assert peak.defensive_active is not None
    assert peak.verdict == "ok"


def test_barrier_on_cooldown_is_not_ready():
    """Barreira usada 10 s antes (recarga de 25 s): nenhum defensivo pronto."""
    data = fight(
        hits=[(POSSESSION, 30, 400, 600), (DEPTHS, 32, 300, 300)],
        heals=[(33, 500)],
        casts=[(BARRIER, 20)],
        buffs=[(BARRIER, "applybuff", 20), (BARRIER, "removebuff", 25)],
    )
    [peak] = damage_peaks(data, RULES, NEKZALI)
    assert peak.defensives_ready == ()
    assert peak.verdict == "ok"


def test_talent_defensive_only_counts_if_used_in_the_fight():
    """Ice Block só conta como disponível se o jogador o usou na luta (pode não ter o talento)."""
    hits = [(POSSESSION, 30, 400, 600), (DEPTHS, 32, 300, 300)]
    barrier_used = [(BARRIER, 20)]
    without = damage_peaks(fight(hits=hits, casts=barrier_used), RULES, NEKZALI)[0]
    with_block = damage_peaks(
        fight(hits=hits, casts=[*barrier_used, (ICE_BLOCK, 50)]), RULES, NEKZALI
    )[0]
    assert without.defensives_ready == ()
    assert len(with_block.defensives_ready) == 1


def test_avoidable_damage_makes_an_avoidable_peak():
    """Poça do Latent Cultist: o erro é de posicionamento, não de defensivo."""
    data = fight(hits=[(CULTIST, 30, 500, 500), (RITE, 31, 200, 300)])
    [peak] = damage_peaks(data, RULES, NEKZALI)
    assert peak.verdict == "evitavel"
    assert peak.avoidable_share == pytest.approx(500 / 700)
    assert avoidable_pct_hp_per_min(data, NEKZALI) == pytest.approx(50)  # 50% da vida em 1 min


def test_low_hp_for_long_with_little_healing_is_a_healing_problem():
    """Barreira já usada, vida a 20% por 6 s quase sem cura: faltou cura, não é erro do Mago."""
    data = fight(
        hits=[(POSSESSION, 30, 400, 600), (DEPTHS, 31, 400, 200), (RITE, 37, 0, 200)],
        heals=[(37, 50)],
        casts=[(BARRIER, 20)],
    )
    [peak] = damage_peaks(data, RULES, NEKZALI)
    assert peak.low_heal is True
    assert peak.verdict == "cura"


def test_low_hp_alone_is_a_peak():
    """Vida abaixo de 35% conta como pico mesmo sem 60% de dano na janela."""
    data = fight(hits=[(RITE, 30, 300, 300)])
    [peak] = damage_peaks(data, RULES, NEKZALI)
    assert peak.min_hp_pct == pytest.approx(30)


def test_drop_after_a_healed_hit_is_not_hidden():
    """Golpe de 65% curado (vida a 60%) e, 6 s depois, queda a 30%: o pico mostra a queda."""
    data = fight(
        hits=[(POSSESSION, 30, 650, 350), (RITE, 36, 300, 300)],
        heals=[(31, 250)],
    )
    [peak] = damage_peaks(data, RULES, NEKZALI)
    assert peak.min_hp_pct == pytest.approx(30)
    assert peak.verdict == "defensivo"


def test_long_chain_of_damage_becomes_several_peaks():
    """Dano contínuo por um minuto não vira um pico só (o grupo fecha pelo primeiro candidato)."""
    hits = [(RITE, t, 650, 600) for t in range(0, 60, 5)]
    assert len(damage_peaks(fight(hits=hits, heals=[]), RULES, NEKZALI)) >= 5


def test_barrier_after_the_drop_does_not_cover_it():
    """Barreira posta só depois da vida mínima: não conta como coberto; aparece como tardia."""
    data = fight(
        hits=[(POSSESSION, 30, 400, 600), (DEPTHS, 32, 300, 300)],
        casts=[(BARRIER, 33)],
        buffs=[(BARRIER, "applybuff", 33), (BARRIER, "removebuff", 40)],
    )
    [peak] = damage_peaks(data, RULES, NEKZALI)
    assert peak.defensive_active is None
    assert peak.defensive_late is not None


def test_absorbed_shields_are_not_healing():
    """Escudo absorvido já sai do dano recebido: não pode subir a vida de novo."""
    data = fight(hits=[(POSSESSION, 30, 400, 600), (DEPTHS, 31, 400, 200)])
    data["events"]["healing_taken"] = [
        {"type": "absorbed", "abilityGameID": 17, "timestamp": 31000, "amount": 500}
    ]
    [peak] = damage_peaks(data, RULES, NEKZALI)
    assert peak.min_hp_pct == pytest.approx(20)
    assert peak.heal_pct_hp == 0


def test_heal_is_capped_by_the_max_hp_of_the_moment():
    """Vida máxima maior por um buff (1200): a cura não derruba a vida para a mediana (1000)."""
    data = fight(hits=[(RITE, t, 0, 1000) for t in range(0, 50, 5)] + [(RITE, 51, 300, 900)])
    for event in data["events"]["damage_taken"][-1:]:
        event["maxHitPoints"] = 1200
    data["events"]["healing_taken"] = [
        {"type": "heal", "abilityGameID": 1, "timestamp": 52000, "amount": 250}
    ]
    from app.engine.defensives import _hp_series

    assert _hp_series(data, 1000)[-1][1:] == (1150, 1200)


def test_avoidable_damage_has_a_floor_when_tops_take_none():
    """Tops com 0 de dano evitável: um pouco (0,5% da vida por minuto) não vira erro."""
    data = fight(hits=[(CULTIST, 30, 5, 995)])
    player = measure(data, RULES, NEKZALI)
    tops = [measure(fight(), RULES, NEKZALI) for _ in range(5)]
    check = next(c for c in run_checks(player, tops, RULES, NEKZALI) if c.id == "avoidable_damage")
    assert check.status == "ok"


def test_peak_text_in_portuguese():
    data = fight(hits=[(POSSESSION, 30, 400, 600), (DEPTHS, 32, 300, 300)], casts=[(ICE_BLOCK, 5)])
    data["events"]["casts"][0]["timestamp"] = -300_000  # Ice Block usado há muito: disponível
    checks = run_checks(measure(data, RULES, NEKZALI), [], RULES, NEKZALI)
    check = next(c for c in checks if c.id == "damage_peaks")
    assert check.player_value.startswith("1 pico:")
    assert "disponíveis)" in check.details[0]
    assert "vida caiu a 30%" in check.details[0]


def test_fight_without_hit_points_has_no_peaks():
    data = fight(hits=[(POSSESSION, 30, 700, 300)])
    for event in data["events"]["damage_taken"]:
        del event["maxHitPoints"], event["hitPoints"]
    assert damage_peaks(data, RULES, NEKZALI) == []


# --- Kill de referência ----------------------------------------------------------------------


@lru_cache
def load(name: str) -> dict:
    return json.loads(gzip.decompress((FIXTURES / name).read_bytes()))


def test_reference_kill_peaks():
    """Fixtures de 03/11: 8 picos no Harmonist; o das 5:06 é a poça (Latent Cultist, Barreira só
    depois da queda), o das 6:39 (vida a 44%, Barreira disponível) é o único em que o defensivo
    cabia e nos outros 6 a cura segurou (vida mínima de 54% a 76%)."""
    data = load("reference_harmonist.json.gz")
    peaks = damage_peaks(data, RULES, NEKZALI)
    assert len(peaks) == 8
    by_verdict = {p.verdict for p in peaks if p.verdict != "ok"}
    assert by_verdict == {"evitavel", "defensivo"}
    cultist = next(p for p in peaks if p.verdict == "evitavel")
    assert round(cultist.time_s) == 306
    assert cultist.mechanics[0].ability_id == CULTIST
    assert cultist.defensive_active is None  # a Barreira veio depois da queda
    assert cultist.defensive_late is not None
    defensive = next(p for p in peaks if p.verdict == "defensivo")
    assert round(defensive.time_s) == 399
    assert defensive.min_hp_pct < 50
    assert avoidable_pct_hp_per_min(data, NEKZALI) == pytest.approx(25.9, abs=0.2)


def test_reference_kill_avoidable_damage_is_an_error_against_the_tops():
    player = measure(load("reference_harmonist.json.gz"), RULES, NEKZALI)
    tops = [measure(load(f"top{i:02d}.json.gz"), RULES, NEKZALI) for i in range(1, 11)]
    check = next(c for c in run_checks(player, tops, RULES, NEKZALI) if c.id == "avoidable_damage")
    assert check.status == "erro"  # 25,9% da vida por minuto; pior top 15,2%
