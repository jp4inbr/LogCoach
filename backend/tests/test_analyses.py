from datetime import UTC, datetime, timedelta

import pytest
from conftest import ANALYSIS, make_result
from sqlmodel import Session
from test_sources import FakeWcl, nekzali

from app.main import app
from app.models import Analysis
from app.schemas import AnalysisResult, FightOption, PlayerOption, ReportResolved
from app.services import analyzer as analyzer_module
from app.services.analyzer import get_analyzer
from app.services.plan import month_start
from app.services.sources import (
    QUERY_LIMIT,
    REFRESH_MIN_INTERVAL_S,
    SAMPLE_REPORT_CODE,
    SampleReportSource,
    SourceUnavailableError,
    build_players,
    build_report,
    get_report_source,
)


@pytest.fixture
def real_engine():
    """Pede o motor de verdade (`engine.report.build_analysis`) em vez do falso."""


@pytest.fixture(autouse=True)
def fake_engine(request, monkeypatch):
    """O motor falso devolve um resultado mínimo com o cabeçalho e a comparação que o
    `EngineAnalyzer` montou (rotas, erros e histórico não dependem das contas do motor)."""
    if "real_engine" in request.fixturenames:
        return

    def build(*, report_code, fight_info, player_info, comparison, **_):
        return make_result(comparison, fight_info, player_info, report_code)

    monkeypatch.setattr(analyzer_module, "build_analysis", build)


def test_analysis_without_account_is_not_saved_to_history(client):
    response = client.post("/analyses", json=ANALYSIS)

    assert response.status_code == 201
    body = response.json()
    assert body["saved"] is False
    assert body["result"]["player"]["name"] == "Harmonist"
    # A análise sem conta ainda abre pelo id (link da tela de resultado).
    assert client.get(f"/analyses/{body['id']}").status_code == 200


def test_rf25_player_is_never_hidden_and_tops_come_without_real_names(client):
    result = client.post("/analyses", json=ANALYSIS).json()["result"]

    assert result["player"]["display_name"] == result["player"]["name"] == "Harmonist"
    tops = result["comparison"]["players"]
    assert len(tops) == 10
    assert [t["display_name"] for t in tops] == [f"top{n:02d}" for n in range(1, 11)]
    # No exemplo não há nome real: o botão de mostrar nomes fica desabilitado.
    assert all(t["name"] is None for t in tops)
    assert result["comparison"]["sample"] is True
    assert result["comparison"]["size"] == 10
    assert result["source"] == "motor"


def test_invalid_token_on_public_route_counts_as_no_login(client):
    response = client.post(
        "/analyses", json=ANALYSIS, headers={"Authorization": "Bearer token-vencido"}
    )

    assert response.status_code == 201
    assert response.json()["saved"] is False


def test_analysis_with_account_goes_to_history(client, auth_headers):
    created = client.post("/analyses", json=ANALYSIS, headers=auth_headers).json()

    history = client.get("/me/analyses", headers=auth_headers).json()
    me = client.get("/me", headers=auth_headers).json()

    assert created["saved"] is True
    assert [item["id"] for item in history] == [created["id"]]
    assert history[0]["boss"] == "Nek'zali, a Enrosca-almas"
    assert history[0]["mistakes_count"] == len(created["result"]["mistakes"])
    assert me["analyses_this_month"] == 1


def test_other_account_cannot_open_my_analysis(client, auth_headers):
    created = client.post("/analyses", json=ANALYSIS, headers=auth_headers).json()
    other = client.post(
        "/auth/register", json={"email": "outro@exemplo.com", "password": "senha-forte-2"}
    ).json()

    response = client.get(
        f"/analyses/{created['id']}",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )

    assert response.status_code == 404
    assert client.get(f"/analyses/{created['id']}").status_code == 404


def test_t08_sixth_analysis_in_the_month_is_blocked(client, auth_headers):
    for _ in range(5):
        assert client.post("/analyses", json=ANALYSIS, headers=auth_headers).status_code == 201

    response = client.post("/analyses", json=ANALYSIS, headers=auth_headers)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "plan_limit"


def test_plan_limit_is_checked_before_asking_the_warcraft_logs(client, auth_headers):
    # Quem já não pode analisar não gasta pontos: nem a lista nem os Magos são buscados.
    for _ in range(5):
        assert client.post("/analyses", json=ANALYSIS, headers=auth_headers).status_code == 201
    wcl = FakeWcl()
    source = wcl.source()
    app.dependency_overrides[get_report_source] = lambda: source

    response = client.post(
        "/analyses",
        json={**ANALYSIS, "report_code": "TESTE123", "fight_id": 2, "actor_id": 10},
        headers=auth_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "plan_limit"
    assert wcl.calls == []


def test_analysis_counts_in_the_query_limit(client):
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    app.dependency_overrides[get_report_source] = lambda: source
    for _ in range(QUERY_LIMIT):
        now[0] += REFRESH_MIN_INTERVAL_S
        assert (
            client.post(
                "/reports/resolve", json={"url": "https://www.warcraftlogs.com/reports/TESTE123"}
            ).status_code
            == 200
        )

    response = client.post("/analyses", json={**ANALYSIS, "report_code": "TESTE123", "fight_id": 2,
                                              "actor_id": 10})  # fmt: skip

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "query_limit"
    assert wcl.count("FightPlayers") == 0


def test_t08_previous_month_does_not_count(client, auth_headers, engine):
    analysis_id = client.post("/analyses", json=ANALYSIS, headers=auth_headers).json()["id"]
    with Session(engine) as session:
        analysis = session.get(Analysis, analysis_id)
        analysis.created_at = month_start() - timedelta(days=1)
        session.add(analysis)
        session.commit()

    me = client.get("/me", headers=auth_headers).json()

    assert me["analyses_this_month"] == 0


def test_t09_short_fight_is_refused(client):
    response = client.post("/analyses", json={**ANALYSIS, "fight_id": 33})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "fight_too_short"


def test_unsupported_boss_is_refused(client):
    response = client.post("/analyses", json={**ANALYSIS, "fight_id": 41})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_fight"


def test_t10_player_not_in_fight(client):
    response = client.post("/analyses", json={**ANALYSIS, "actor_id": 999})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "no_arcane_mage"


def test_request_without_actor_id_is_refused(client):
    # O nome sozinho não serve mais: o jogador vem sempre pelo id do ator.
    request = {"report_code": ANALYSIS["report_code"], "fight_id": 34, "player_name": "Harmonist"}

    assert client.post("/analyses", json=request).status_code == 422


def test_delete_account_removes_analyses(client, auth_headers, engine):
    created = client.post("/analyses", json=ANALYSIS, headers=auth_headers).json()

    response = client.delete("/me", headers=auth_headers)

    assert response.status_code == 204
    assert client.get("/me", headers=auth_headers).status_code == 401
    with Session(engine) as session:
        assert session.get(Analysis, created["id"]) is None


def arcane(actor_id: int, name: str, server: str) -> PlayerOption:
    return PlayerOption(
        actor_id=actor_id, name=name, server=server, spec="Mago Arcano", item_level=327
    )


class SpyAnalyzer:
    """Guarda o jogador que a rota escolheu e devolve um resultado mínimo."""

    players: list[PlayerOption] = []

    def analyze(self, report, fight, player: PlayerOption) -> AnalysisResult:
        SpyAnalyzer.players.append(player)
        return make_result(report_code=report.code)


@pytest.fixture
def spy_analyzer():
    SpyAnalyzer.players = []
    app.dependency_overrides[get_analyzer] = SpyAnalyzer
    return SpyAnalyzer


class OneFightSource:
    """Relatório sintético com a luta 34 e os Magos Arcanos dados; os eventos são os do
    exemplo (só o Harmonist, ator 455, tem)."""

    players: list[PlayerOption] = []

    def get_report(self, code: str, refresh: bool = False, client=None) -> ReportResolved:
        fight = FightOption(
            id=34,
            boss="Nek'zali, a Enrosca-almas",
            difficulty="Mítico",
            encounter_id=3470,
            difficulty_id=5,
            kill=True,
            duration_s=415.0,
            supported=True,
        )
        return ReportResolved(
            code=SAMPLE_REPORT_CODE, title="Sintético", sample=True, fights=[fight]
        )

    def get_fight_players(self, code: str, fight_id: int, client=None) -> list[PlayerOption]:
        return self.players

    def get_fight_data(self, code: str, fight_id: int, actor_id: int) -> dict:
        return SampleReportSource().get_fight_data(code, fight_id, actor_id)


class TwoHarmonistsSource(OneFightSource):
    """Dois Magos Arcanos de mesmo nome em reinos diferentes."""

    players = [arcane(455, "Harmonist", "Area 52"), arcane(456, "Harmonist", "Tichondrius")]


def test_homonyms_are_told_apart_by_actor_id(client, spy_analyzer):
    app.dependency_overrides[get_report_source] = TwoHarmonistsSource

    for actor_id in (456, 455):
        assert client.post("/analyses", json={**ANALYSIS, "actor_id": actor_id}).status_code == 201

    assert [(p.actor_id, p.server) for p in spy_analyzer.players] == [
        (456, "Tichondrius"),
        (455, "Area 52"),
    ]


# Respostas falsas do REPORT_FIGHTS e do FIGHT_PLAYERS: na luta 2 há um Arcano, um Fogo e
# um Guerreiro; o outro Arcano (id 13) só está na luta 1.
RAW_REPORT = {
    "code": SAMPLE_REPORT_CODE,
    "title": "Sintético",
    "fights": [
        {"id": 1, "encounterID": 3470, "name": "Nek'zali", "difficulty": 5, "kill": False,
         "startTime": 0, "endTime": 90_000},
        {"id": 2, "encounterID": 3470, "name": "Nek'zali", "difficulty": 5, "kill": True,
         "startTime": 100_000, "endTime": 515_000},
    ],
}  # fmt: skip
RAW_ACTORS = [
    {"id": 10, "name": "arcano_a", "server": "Norte", "type": "Player", "subType": "Mage"},
    {"id": 11, "name": "fogo_a", "server": "Norte", "type": "Player", "subType": "Mage"},
    {"id": 13, "name": "arcano_b", "server": "Sul", "type": "Player", "subType": "Mage"},
]
RAW_PLAYERS = {
    1: [{"id": 10, "spec": "Arcane", "item_level": 327}, {"id": 13, "spec": "Arcane",
        "item_level": 327}],
    2: [{"id": 10, "spec": "Arcane", "item_level": 327}, {"id": 11, "spec": "Fire",
        "item_level": 327}, {"id": 12, "spec": "Arms", "item_level": 327}],
}  # fmt: skip


class RawReportSource:
    def get_report(self, code: str, refresh: bool = False, client=None) -> ReportResolved:
        encounters = {3470: {"boss_npc_id": None, "difficulties": [5]}}
        return ReportResolved.model_validate(build_report(RAW_REPORT, encounters, {}))

    def get_fight_players(self, code: str, fight_id: int, client=None) -> list[PlayerOption]:
        raw = {"fight_id": fight_id, "players": RAW_PLAYERS[fight_id], "actors": RAW_ACTORS}
        return [PlayerOption.model_validate(p) for p in build_players(raw)]


@pytest.mark.parametrize("actor_id", [11, 12, 13, 999])
def test_actor_that_is_not_an_arcane_of_the_fight_is_refused(client, spy_analyzer, actor_id):
    # 11 é Fogo, 12 é Guerreiro, 13 é Arcano de outra luta, 999 não existe no report.
    app.dependency_overrides[get_report_source] = RawReportSource

    response = client.post("/analyses", json={**ANALYSIS, "fight_id": 2, "actor_id": actor_id})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "no_arcane_mage"
    assert spy_analyzer.players == []


def test_arcane_of_the_fight_is_found_by_actor_id(client, spy_analyzer):
    app.dependency_overrides[get_report_source] = RawReportSource

    response = client.post("/analyses", json={**ANALYSIS, "fight_id": 2, "actor_id": 10})

    assert response.status_code == 201
    assert [p.name for p in spy_analyzer.players] == ["arcano_a"]


class HarmonistAndOtherSource(OneFightSource):
    """Luta 34 sintética com o Harmonist e outro Arcano (pseudônimo)."""

    players = [
        # Com DATA_SOURCE=wcl o Harmonist chega com reino; o exemplo não tem reino.
        arcane(455, "Harmonist", "Azralon"),
        arcane(456, "Outroarcano", "Area 52"),
    ]


def test_other_arcane_in_sample_fight_does_not_get_harmonist_result(client, auth_headers):
    # Sem os eventos dele (só o Harmonist tem no exemplo): o motor não usa os de outro.
    app.dependency_overrides[get_report_source] = HarmonistAndOtherSource

    response = client.post("/analyses", json={**ANALYSIS, "actor_id": 456}, headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "analysis_not_available"
    # Recusada antes de gravar: não entra no histórico nem conta no limite do plano.
    assert client.get("/me", headers=auth_headers).json()["analyses_this_month"] == 0
    assert client.get("/me/analyses", headers=auth_headers).json() == []


def test_harmonist_in_sample_fight_still_gets_the_result(client):
    app.dependency_overrides[get_report_source] = HarmonistAndOtherSource

    response = client.post("/analyses", json=ANALYSIS)

    assert response.status_code == 201
    assert response.json()["result"]["player"]["name"] == "Harmonist"


class DownSource:
    def get_report(self, code: str, refresh: bool = False, client=None) -> ReportResolved:
        raise SourceUnavailableError(code)

    def get_fight_players(self, code: str, fight_id: int, client=None) -> list[PlayerOption]:
        raise SourceUnavailableError(code)


# --- Luta fora do cache (log ao vivo) ---------------------------------------------


def wcl_source(wcl: FakeWcl, now: list[float]):
    source = wcl.source(clock=now)
    app.dependency_overrides[get_report_source] = lambda: source
    return source


def test_fight_missing_from_cache_refreshes_the_list_once(client, spy_analyzer):
    # O usuário abriu o log antes do pull; a luta nova não está na lista guardada.
    now = [0.0]
    wcl = FakeWcl(report={**FakeWcl().report, "code": SAMPLE_REPORT_CODE})
    wcl_source(wcl, now).get_report(SAMPLE_REPORT_CODE)
    wcl.report["fights"].append(nekzali(5, 1_300_000, 1_450_000))
    wcl.fight_players[5] = ([10], ["Arcane"], [327])
    now[0] = 120

    response = client.post("/analyses", json={**ANALYSIS, "fight_id": 5, "actor_id": 10})

    assert response.status_code == 201
    assert wcl.calls == ["ReportFights", "ReportFights", "FightPlayers"]


def test_fight_that_does_not_exist_is_searched_only_once(client, spy_analyzer):
    now = [0.0]
    wcl = FakeWcl(report={**FakeWcl().report, "code": SAMPLE_REPORT_CODE})
    wcl_source(wcl, now).get_report(SAMPLE_REPORT_CODE)
    now[0] = 120

    response = client.post("/analyses", json={**ANALYSIS, "fight_id": 99, "actor_id": 10})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "fight_not_found"
    assert wcl.calls == ["ReportFights", "ReportFights"]


def test_analysis_uses_the_cached_fight_players(client, spy_analyzer):
    # A tela já buscou os Magos da luta; o /analyses não consulta o WCL de novo.
    wcl = FakeWcl(report={**FakeWcl().report, "code": SAMPLE_REPORT_CODE})
    source = wcl_source(wcl, [0.0])
    source.get_report(SAMPLE_REPORT_CODE)
    source.get_fight_players(SAMPLE_REPORT_CODE, 2)

    response = client.post("/analyses", json={**ANALYSIS, "fight_id": 2, "actor_id": 13})

    assert response.status_code == 201
    assert wcl.calls == ["ReportFights", "FightPlayers"]


def test_analysis_with_wcl_down_is_wcl_unavailable(client, auth_headers):
    app.dependency_overrides[get_report_source] = DownSource

    response = client.post("/analyses", json=ANALYSIS, headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "wcl_unavailable"
    assert client.get("/me", headers=auth_headers).json()["analyses_this_month"] == 0


# --- Motor de verdade (modo exemplo: SampleReportSource + SampleTopsSource) -------------


def test_e2e_harmonist_gets_the_engine_result(client, real_engine):
    response = client.post("/analyses", json=ANALYSIS)

    assert response.status_code == 201
    result = response.json()["result"]
    assert result["source"] == "motor"
    assert result["player"]["display_name"] == result["player"]["name"] == "Harmonist"
    comparison = result["comparison"]
    assert (comparison["size"], comparison["sample"], comparison["player_in_top"]) == (
        10,
        True,
        False,
    )
    tops = comparison["players"]
    assert [t["display_name"] for t in tops] == [f"top{n:02d}" for n in range(1, 11)]
    avg = sum(t["dps"] for t in tops) / len(tops)
    assert result["summary"]["top_avg_dps"] == pytest.approx(avg, abs=0.1)
    assert result["gap"] is not None


def test_e2e_t06_mistakes_come_sorted_by_impact(client, real_engine):
    mistakes = client.post("/analyses", json=ANALYSIS).json()["result"]["mistakes"]

    # Regras do maior para o menor impacto (risco sem impacto no fim); hipóteses depois.
    kinds = [m["kind"] for m in mistakes]
    assert kinds == sorted(kinds, key=lambda kind: kind == "hipotese")
    rules = [m["impact_pct"] for m in mistakes if m["kind"] == "regra"]
    impacts = [-1 if impact is None else impact for impact in rules]
    assert impacts == sorted(impacts, reverse=True)


def test_month_start():
    assert month_start(datetime(2026, 10, 26, 17, 30, tzinfo=UTC)) == datetime(
        2026, 10, 1, tzinfo=UTC
    )
