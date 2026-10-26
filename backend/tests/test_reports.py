import pytest

from app.services.links import parse_report_code


@pytest.mark.parametrize(
    "url",
    [
        "https://www.warcraftlogs.com/reports/AbC123",  # T01 (entrada do item 10)
        "https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=34&type=damage-done",
        "warcraftlogs.com/reports/XhrmBaYkGCAQjH2D",
        "  https://classic.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D/  ",
    ],
)
def test_t01_link_validator_accepts_valid_links(url):
    assert parse_report_code(url) is not None


@pytest.mark.parametrize(
    "url",
    [
        "https://google.com",  # T02
        "https://www.warcraftlogs.com/character/us/stormrage/harmonist",
        "https://warcraftlogs.com.golpe.net/reports/XhrmBaYkGCAQjH2D",
        "",
    ],
)
def test_t02_link_validator_rejects_other_links(url):
    assert parse_report_code(url) is None


def test_resolve_lists_fights_and_marks_unsupported(client):
    response = client.post(
        "/reports/resolve",
        json={"url": "https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=34"},
    )

    assert response.status_code == 200
    body = response.json()
    fights = {f["id"]: f for f in body["fights"]}
    assert body["sample"] is True
    assert fights[34]["supported"] is True
    assert fights[34]["players"][0]["name"] == "Harmonist"
    assert "server" in fights[34]["players"][0]
    assert fights[41]["supported"] is False
    assert fights[41]["unsupported_reason"] == "Chefe ainda não suportado"


def test_resolve_rejects_link_from_other_site(client):
    response = client.post("/reports/resolve", json={"url": "https://google.com"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_link"


def test_resolve_unknown_report(client):
    response = client.post(
        "/reports/resolve", json={"url": "https://www.warcraftlogs.com/reports/OutroRelatorio1"}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "report_not_available"
