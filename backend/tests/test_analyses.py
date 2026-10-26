from datetime import UTC, datetime, timedelta

import pytest
from conftest import ANALYSIS
from sqlmodel import Session

from app.main import app
from app.models import Analysis
from app.schemas import FightOption, PlayerOption, ReportResolved
from app.services.plan import month_start
from app.services.sources import SAMPLE_REPORT_CODE, get_report_source


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
    avg = sum(t["dps"] for t in tops) / len(tops)
    assert result["summary"]["top_avg_dps"] == pytest.approx(avg, abs=0.1)


def test_invalid_token_on_public_route_counts_as_no_login(client):
    response = client.post(
        "/analyses", json=ANALYSIS, headers={"Authorization": "Bearer token-vencido"}
    )

    assert response.status_code == 201
    assert response.json()["saved"] is False


def test_t06_mistakes_come_sorted_by_impact(client):
    mistakes = client.post("/analyses", json=ANALYSIS).json()["result"]["mistakes"]

    impacts = [m["impact_pct"] if m["impact_pct"] is not None else -1 for m in mistakes]
    assert impacts == sorted(impacts, reverse=True)


def test_analysis_with_account_goes_to_history(client, auth_headers):
    created = client.post("/analyses", json=ANALYSIS, headers=auth_headers).json()

    history = client.get("/me/analyses", headers=auth_headers).json()
    me = client.get("/me", headers=auth_headers).json()

    assert created["saved"] is True
    assert [item["id"] for item in history] == [created["id"]]
    assert history[0]["boss"] == "Nek'zali, a Enrosca-almas"
    assert history[0]["mistakes_count"] == 5
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
    response = client.post("/analyses", json={**ANALYSIS, "player_name": "Ninguem"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "no_arcane_mage"


def test_delete_account_removes_analyses(client, auth_headers, engine):
    created = client.post("/analyses", json=ANALYSIS, headers=auth_headers).json()

    response = client.delete("/me", headers=auth_headers)

    assert response.status_code == 204
    assert client.get("/me", headers=auth_headers).status_code == 401
    with Session(engine) as session:
        assert session.get(Analysis, created["id"]) is None


class TwoSombrasSource:
    """Relatório sintético com dois Magos Arcanos de mesmo nome em reinos diferentes."""

    def get_report(self, code: str) -> ReportResolved:
        players = [
            PlayerOption(name="Sombra", server="Area 52", spec="Mago Arcano", item_level=327),
            PlayerOption(name="Sombra", server="Tichondrius", spec="Mago Arcano", item_level=327),
        ]
        fight = FightOption(
            id=34,
            boss="Nek'zali, a Enrosca-almas",
            difficulty="Mítico",
            kill=True,
            duration_s=415.0,
            supported=True,
            players=players,
        )
        return ReportResolved(
            code=SAMPLE_REPORT_CODE, title="Sintético", sample=True, fights=[fight]
        )


def test_repeated_name_without_server_is_ambiguous(client):
    app.dependency_overrides[get_report_source] = TwoSombrasSource
    request = {**ANALYSIS, "player_name": "Sombra"}

    without_server = client.post("/analyses", json=request)
    wrong_server = client.post("/analyses", json={**request, "server": "Azralon"})
    with_server = client.post("/analyses", json={**request, "server": "area-52"})

    assert without_server.status_code == 422
    assert without_server.json()["detail"]["code"] == "player_ambiguous"
    assert wrong_server.json()["detail"]["code"] == "player_ambiguous"
    assert with_server.status_code == 201


def test_month_start():
    assert month_start(datetime(2026, 10, 26, 17, 30, tzinfo=UTC)) == datetime(
        2026, 10, 1, tzinfo=UTC
    )
