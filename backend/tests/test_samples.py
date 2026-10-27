"""Coerência do resultado de exemplo (app/samples/analysis_*.json).

O exemplo aparece na demo e na banca: a conta tem que fechar mesmo sendo montado à mão.
"""

import json
from pathlib import Path

import pytest

from app.schemas import AnalysisResult

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "app" / "samples"
SAMPLE_FILES = sorted(SAMPLES_DIR.glob("analysis_*.json"))

# Erro de regra → item da lista de regras, quando os ids diferem.
RULE_OF_MISTAKE = {
    "late_second_potion": "second_potion",
    "overlap_no_defensive": "overlap_defensive",
}


def load(path: Path) -> AnalysisResult:
    return AnalysisResult.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.fixture(params=SAMPLE_FILES, ids=lambda path: path.name)
def sample(request) -> AnalysisResult:
    return load(request.param)


def test_there_is_a_sample_analysis():
    assert SAMPLE_FILES


def test_impacts_add_up_to_the_dps_gap(sample):
    # RF23: o que as regras não explicam fica na hipótese, então a soma fecha com a diferença.
    impacts = [m.impact_pct for m in sample.mistakes if m.impact_pct is not None]
    assert sum(impacts) == pytest.approx(abs(sample.summary.dps_gap_pct), abs=0.1)


def test_mistakes_sorted_by_impact_with_risk_last(sample):
    impacts = [m.impact_pct for m in sample.mistakes]
    known = [i for i in impacts if i is not None]
    assert known == sorted(known, reverse=True)
    # Os sem impacto (risco, não dano) ficam no fim.
    assert impacts[len(known) :] == [None] * (len(impacts) - len(known))


def test_reference_sample_has_five_mistakes():
    result = load(SAMPLES_DIR / "analysis_XhrmBaYkGCAQjH2D_34.json")
    assert len(result.mistakes) == 5


def test_rule_mistakes_point_to_a_rule_that_is_not_ok(sample):
    rules = {rule.id: rule for rule in sample.rules}
    for mistake in sample.mistakes:
        if mistake.kind != "regra":
            continue
        rule_id = RULE_OF_MISTAKE.get(mistake.id, mistake.id)
        assert rule_id in rules, f"{mistake.id} sem regra correspondente"
        assert rules[rule_id].status != "ok", f"{mistake.id} listado como erro, regra ok"


def test_versioned_sample_has_no_real_names(sample):
    # RF25: nomes reais só vêm do names.local.json da máquina, nunca do arquivo no git.
    assert all(player.name is None for player in sample.comparison.players)
