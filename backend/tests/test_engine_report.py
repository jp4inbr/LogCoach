"""`engine/report.py`: o `AnalysisResult` do motor a partir do kill de referência e dos tops."""

import gzip
import json
from functools import lru_cache
from pathlib import Path

import pytest

from app.engine.report import build_analysis
from app.engine.rules import load_encounter_rules, load_spec_rules
from app.schemas import AnalysisResult, ComparedPlayer, Comparison, FightInfo, PlayerInfo

FIXTURES = Path(__file__).parent / "fixtures" / "nekzali_mythic_326_328"
RULES = load_spec_rules()
NEKZALI = load_encounter_rules(3470)
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))


@lru_cache
def load(name: str) -> dict:
    return json.loads(gzip.decompress((FIXTURES / name).read_bytes()))


def comparison(size: int = 10) -> Comparison:
    tops = INDEX["top"][:size]
    return Comparison(
        label="Top 10 do bracket 326–328",
        bracket="326–328",
        size=len(tops),
        player_in_top=False,
        players=[
            ComparedPlayer(
                rank=t["rank"],
                display_name=t["display_name"],
                name=f"NomeReal{t['rank']}",  # RF25: só o botão de olho mostra
                dps=t["amount"],
            )
            for t in tops
        ],
    )


def top_fights(size: int = 10):
    """Gerador, como o `EngineAnalyzer` entrega: uma luta por vez."""
    for t in INDEX["top"][:size]:
        yield load(t["file"]), t["amount"]


def build(size: int = 10) -> AnalysisResult:
    fight = load("reference_harmonist.json.gz")
    return build_analysis(
        report_code="XhrmBaYkGCAQjH2D",
        fight_info=FightInfo(
            id=34, boss="Nek'zali", difficulty="Mítico", kill=True, duration_s=415.6
        ),
        player_info=PlayerInfo(name="Harmonist", spec="Arcano", item_level=327),
        comparison=comparison(size),
        player_fight=fight,
        top_fights=top_fights(size),
        encounter=NEKZALI,
        rules=RULES,
    )


@lru_cache
def reference() -> AnalysisResult:
    return build()


def test_reference_kill_result_validates_and_has_the_gap():
    result = AnalysisResult.model_validate(reference().model_dump())
    assert result.source == "motor"
    assert result.coach.available is False
    gap = result.gap
    assert gap.total_pct == pytest.approx(18.0, abs=0.1)
    assert gap.mistakes_pct == pytest.approx(6.6, abs=0.1)
    assert gap.luck_pct == pytest.approx(9.5, abs=0.1)
    assert gap.unexplained_pct == pytest.approx(1.9, abs=0.1)
    assert result.summary.dps == pytest.approx(225_680.6, abs=0.1)
    assert result.summary.dps_gap_pct < 0
    assert 0 < result.summary.active_time_pct <= 100
    assert {r.id for r in result.rules} >= {"soul_entry", "surge_blasts", "barrage_low_salvo"}
    assert result.abilities and result.targets
    assert any(row.boss for table in result.targets for row in table.rows)


def test_mistakes_are_ordered_and_end_with_the_hypothesis():
    mistakes = reference().mistakes
    rules = [m for m in mistakes if m.kind == "regra"]
    assert mistakes[-1].id == "unexplained_gap" and mistakes[-1].kind == "hipotese"
    assert mistakes[-1].impact_pct == pytest.approx(1.9, abs=0.1)
    with_impact = [m.impact_pct for m in rules if m.impact_pct is not None]
    assert with_impact == sorted(with_impact, reverse=True)
    # Os sem impacto (risco) vêm depois de todos os com impacto, erro antes de atenção.
    first_none = next(i for i, m in enumerate(rules) if m.impact_pct is None)
    assert all(m.impact_pct is None for m in rules[first_none:])
    severities = [m.severity for m in rules[first_none:]]
    assert severities == sorted(severities, key=lambda s: s != "erro")
    assert {"soul_entry", "surge_blasts"} <= {m.id for m in rules}
    # A sorte do Prismatic Bolt nunca vira erro (fica só no gap).
    assert not any("sorte" in m.title.lower() or "azar" in m.title.lower() for m in mistakes)


def test_no_real_names_in_the_texts():
    """RF25: fora da `comparison` (que a tela oculta), nenhum nome de outro jogador."""
    result = reference()
    text = result.model_dump_json(exclude={"comparison"})
    assert "NomeReal" not in text
    assert "top0" not in text and "raid_" not in text
    assert "NomeReal1" in result.comparison.model_dump_json()  # a comparação passa intacta


def test_timeline_in_fight_seconds():
    result = reference()
    duration = result.phases[-1].end_s
    surge = next(t for t in result.timeline if t.ability_id == 365350)
    assert surge.player_s and surge.top_s
    for track in result.timeline:
        assert all(0 <= s <= duration for s in track.player_s)
    assert result.phases[0].start_s == 0
    assert [p.intermission for p in result.phases] == [False, True, False]


def test_without_tops_it_still_builds():
    result = build(size=0)
    assert result.summary.top_avg_dps == result.summary.dps
    assert result.summary.top_active_time_pct == result.summary.active_time_pct
    assert result.gap.total_pct == 0
    assert all(t.top_s == [] for t in result.timeline)
    assert result.rules
