"""`EngineAnalyzer` (services/analyzer.py): o que ele entrega ao motor e os erros na rota."""

import gzip
import json

import pytest
from conftest import ANALYSIS, make_result

from app.main import app
from app.schemas import FightOption, PlayerOption, ReportResolved
from app.services import analyzer as analyzer_module
from app.services.analyzer import EngineAnalyzer
from app.services.sources import AnalysisNotAvailableError, SourceUnavailableError
from app.services.tops import (
    OwnLog,
    TopEntry,
    TopsComparison,
    TopsNotAvailableError,
    get_tops_source,
)

REPORT = ReportResolved(code="ABC123", title="Teste", sample=False, fights=[])
FIGHT = FightOption(
    id=7, boss="Nek'zali, a Enrosca-almas", difficulty="Mítico", encounter_id=3470,
    difficulty_id=5, kill=True, duration_s=400.0, supported=True,
)  # fmt: skip
PLAYER = PlayerOption(actor_id=21, name="Fulano", server="Azralon", spec="Mago Arcano",
                      item_level=327)  # fmt: skip


def entry(rank: int) -> TopEntry:
    fight = {"rank": rank}
    return TopEntry(
        rank=rank, display_name=f"top{rank:02d}", name=f"Real{rank}", server="Norte",
        item_level=327, dps=250_000.0 + rank, duration_ms=300_000, report=f"R{rank}",
        fight_id=rank, fight_gz=gzip.compress(json.dumps(fight).encode()),
    )  # fmt: skip


class FakeTops:
    def __init__(self, comparison=None, error=None):
        self.comparison = comparison or TopsComparison(
            label="Top 10 do bracket 326–328", bracket="326–328", player_in_top=True,
            entries=(entry(1), entry(2)), stale=True,
        )  # fmt: skip
        self.error = error
        self.calls = []

    def get_tops(self, encounter_id, difficulty, item_level, own):
        self.calls.append((encounter_id, difficulty, item_level, own))
        if self.error:
            raise self.error
        return self.comparison

    def prefetch_tops(self, *args):
        return None


class FakeSource:
    def __init__(self):
        self.calls = []

    def get_fight_data(self, code, fight_id, actor_id):
        self.calls.append((code, fight_id, actor_id))
        return {"player": {"actor": {"id": actor_id}}}


@pytest.fixture
def engine_calls(monkeypatch):
    calls = []

    def build(**kwargs):
        kwargs["top_fights"] = list(kwargs["top_fights"])
        calls.append(kwargs)
        return make_result(
            kwargs["comparison"], kwargs["fight_info"], kwargs["player_info"], kwargs["report_code"]
        )

    monkeypatch.setattr(analyzer_module, "build_analysis", build)
    return calls


def test_engine_gets_the_player_fight_the_tops_and_the_encounter(engine_calls):
    source, tops = FakeSource(), FakeTops()

    result = EngineAnalyzer(source, tops).analyze(REPORT, FIGHT, PLAYER)

    assert tops.calls == [(3470, 5, 327, OwnLog("ABC123", 7, "Fulano"))]
    assert source.calls == [("ABC123", 7, 21)]
    (call,) = engine_calls
    assert call["report_code"] == "ABC123"
    assert call["fight_info"].id == 7 and call["fight_info"].duration_s == 400.0
    assert (call["player_info"].name, call["player_info"].server) == ("Fulano", "Azralon")
    assert call["player_info"].item_level == 327
    assert call["player_fight"] == {"player": {"actor": {"id": 21}}}
    assert call["top_fights"] == [({"rank": 1}, 250_001.0), ({"rank": 2}, 250_002.0)]
    assert call["encounter"]["encounter_id"] == 3470
    comparison = call["comparison"]
    assert (comparison.size, comparison.player_in_top, comparison.stale) == (2, True, True)
    assert comparison.sample is False
    # Dados ao vivo: o nome real vem do WCL (a tela oculta por padrão, RF25).
    assert [(p.display_name, p.name) for p in comparison.players] == [
        ("top01", "Real1"),
        ("top02", "Real2"),
    ]
    assert result.source == "motor"


def test_sample_comparison_gets_real_names_from_local_file(engine_calls, monkeypatch):
    filled = []
    monkeypatch.setattr(analyzer_module, "fill_real_names", lambda r, f: filled.append(r))
    sample = TopsComparison(label="x", bracket="326–328", player_in_top=False,
                            entries=(entry(1),), sample=True)  # fmt: skip

    EngineAnalyzer(FakeSource(), FakeTops(sample)).analyze(REPORT, FIGHT, PLAYER)
    EngineAnalyzer(FakeSource(), FakeTops()).analyze(REPORT, FIGHT, PLAYER)

    assert len(filled) == 1 and filled[0].comparison.sample


@pytest.mark.parametrize(
    ("fight", "player"),
    [
        (FIGHT.model_copy(update={"encounter_id": None}), PLAYER),  # lista antiga
        (FIGHT.model_copy(update={"difficulty_id": None}), PLAYER),
        (FIGHT.model_copy(update={"encounter_id": 9999}), PLAYER),  # chefe sem YAML
        (FIGHT, PLAYER.model_copy(update={"item_level": None})),  # sem bracket
    ],
)
def test_fight_the_engine_cannot_analyze(engine_calls, fight, player):
    source, tops = FakeSource(), FakeTops()

    with pytest.raises(AnalysisNotAvailableError):
        EngineAnalyzer(source, tops).analyze(REPORT, fight, player)

    # Recusada antes de qualquer consulta.
    assert (tops.calls, source.calls, engine_calls) == ([], [], [])


def test_without_tops_the_fight_is_not_downloaded(engine_calls):
    source = FakeSource()

    with pytest.raises(TopsNotAvailableError):
        EngineAnalyzer(source, FakeTops(error=TopsNotAvailableError("vazio"))).analyze(
            REPORT, FIGHT, PLAYER
        )

    assert source.calls == []


# --- Erros na rota ----------------------------------------------------------------


def test_route_without_tops_is_analysis_not_available(client, auth_headers, engine_calls):
    app.dependency_overrides[get_tops_source] = lambda: FakeTops(
        error=TopsNotAvailableError("ranking vazio")
    )

    response = client.post("/analyses", json=ANALYSIS, headers=auth_headers)

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "analysis_not_available"
    assert "tops" in detail["message"]
    assert client.get("/me", headers=auth_headers).json()["analyses_this_month"] == 0


def test_route_with_tops_from_wcl_down_is_wcl_unavailable(client, auth_headers, engine_calls):
    app.dependency_overrides[get_tops_source] = lambda: FakeTops(
        error=SourceUnavailableError("3470:5:19", "O Warcraft Logs está fora do ar.")
    )

    response = client.post("/analyses", json=ANALYSIS, headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "wcl_unavailable",
        "message": "O Warcraft Logs está fora do ar.",
    }
    assert client.get("/me", headers=auth_headers).json()["analyses_this_month"] == 0


def test_route_with_unexpected_wcl_error_is_500(client, engine_calls):
    app.dependency_overrides[get_tops_source] = lambda: FakeTops(
        error=SourceUnavailableError("3470:5:19", "Erro nosso.", "unexpected_error")
    )

    response = client.post("/analyses", json=ANALYSIS)

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "unexpected_error"


def test_route_does_not_hide_a_bug_of_the_engine(client, auth_headers, monkeypatch):
    # Bug nosso não vira "análise indisponível": é o 500 do UnexpectedErrorMiddleware.
    def broken(**_):
        raise ZeroDivisionError

    monkeypatch.setattr(analyzer_module, "build_analysis", broken)

    response = client.post("/analyses", json=ANALYSIS, headers=auth_headers)

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "unexpected_error"
    assert client.get("/me", headers=auth_headers).json()["analyses_this_month"] == 0
