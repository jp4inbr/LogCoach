"""Erro inesperado do nosso lado: 500 no formato de sempre, com CORS, sem engolir api_error."""

import logging

import pytest
from conftest import LINK
from fastapi.testclient import TestClient

from app.errors import UNEXPECTED_ERROR_MESSAGE
from app.main import app
from app.services.sources import get_report_source

ORIGIN = "http://localhost:5173"


class BrokenSource:
    def get_report(self, code: str, refresh: bool = False, client=None):
        raise RuntimeError("bug de propósito")


@pytest.fixture
def broken_client():
    app.dependency_overrides[get_report_source] = BrokenSource
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_unhandled_exception_is_500_with_code(broken_client, caplog):
    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = broken_client.post("/reports/resolve", json={"url": LINK})

    assert response.status_code == 500
    assert response.json() == {
        "detail": {"code": "unexpected_error", "message": UNEXPECTED_ERROR_MESSAGE}
    }
    # A causa fica no log, nunca na resposta.
    assert "bug de propósito" in caplog.text
    assert "bug de propósito" not in response.text


def test_unexpected_error_keeps_cors_headers(broken_client):
    # Sem CORS o navegador esconde a resposta e o frontend acha que o servidor caiu.
    response = broken_client.post(
        "/reports/resolve", json={"url": LINK}, headers={"Origin": ORIGIN}
    )

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_api_errors_pass_untouched(client):
    response = client.post("/reports/resolve", json={"url": "https://exemplo.com/nada"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_link"


def test_validation_errors_pass_untouched(client):
    response = client.post("/reports/resolve", json={})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_unexpected_message_is_in_portuguese_and_says_what_to_do():
    assert "LogCoach" in UNEXPECTED_ERROR_MESSAGE
    assert "recarregue a página" in UNEXPECTED_ERROR_MESSAGE


def test_shutdown_stops_the_events_then_the_prefetch_then_closes_the_client(monkeypatch):
    calls: list[str] = []
    names = ("stop_shared_client", "shutdown_prefetch", "shutdown_tops", "close_shared_client")
    for name in names:
        monkeypatch.setattr(f"app.main.{name}", lambda name=name: calls.append(name))

    with TestClient(app):
        assert calls == []

    assert calls == list(names)
