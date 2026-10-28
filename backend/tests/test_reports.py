import threading

import pytest
from test_sources import FakeWcl, fresh_wcl_state, nekzali  # noqa: F401 (fixture autouse)

from app.main import app
from app.services.links import parse_report_code
from app.services.sources import (
    IN_PROGRESS_REASON,
    REFRESH_MIN_INTERVAL_S,
    ReportCache,
    SourceUnavailableError,
    get_report_source,
    shutdown_prefetch,
)

SAMPLE_LINK = "https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=34"


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
    response = client.post("/reports/resolve", json={"url": SAMPLE_LINK})

    assert response.status_code == 200
    body = response.json()
    fights = {f["id"]: f for f in body["fights"]}
    assert body["sample"] is True
    assert body["fetched_at"]  # hora da lista, para a tela ("lista de 21:04")
    assert fights[34]["supported"] is True
    # Só a lista de lutas: os Magos vêm por luta, na rota de jogadores.
    assert "players" not in fights[34]
    assert fights[41]["supported"] is False
    assert fights[41]["unsupported_reason"] == "Chefe ainda não suportado"


def test_refresh_in_sample_mode_brings_the_same_fights(client):
    # Botão "Atualizar lutas" no modo exemplo: sem lutas novas e sem erro.
    first = client.post("/reports/resolve", json={"url": SAMPLE_LINK}).json()

    response = client.post("/reports/resolve", json={"url": SAMPLE_LINK, "refresh": True})

    assert response.status_code == 200
    assert response.json()["fights"] == first["fights"]


def test_fight_players_of_the_sample_fight(client):
    response = client.get("/reports/XhrmBaYkGCAQjH2D/fights/34/players")

    assert response.status_code == 200
    body = response.json()
    assert (body["report_code"], body["fight_id"]) == ("XhrmBaYkGCAQjH2D", 34)
    player = body["players"][0]
    assert (player["actor_id"], player["name"], player["item_level"]) == (455, "Harmonist", 327)
    assert "server" in player


@pytest.mark.parametrize(
    ("fight_id", "status", "code"),
    [
        (33, 422, "fight_too_short"),
        (41, 422, "unsupported_fight"),
        (999, 404, "fight_not_found"),
    ],
)
def test_fight_players_only_for_supported_fights(client, fight_id, status, code):
    # Mesmos erros do POST /analyses.
    response = client.get(f"/reports/XhrmBaYkGCAQjH2D/fights/{fight_id}/players")

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_fight_players_of_unknown_report(client):
    response = client.get("/reports/OutroRelatorio1/fights/34/players")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "report_not_available"


LINK = {"url": "https://www.warcraftlogs.com/reports/TESTE123"}


def use_wcl(wcl: FakeWcl, now: list[float]) -> None:
    # Mesma fonte (e mesmos caches) em todos os pedidos do teste, com relógio controlado.
    source = wcl.source(cache=ReportCache(clock=lambda: now[0]))
    app.dependency_overrides[get_report_source] = lambda: source


@pytest.mark.parametrize("body", [{}, {"refresh": True}])
def test_resolve_always_fetches_the_list_again(client, body):
    # Colar o link de novo, "Atualizar lutas" e a atualização automática: com ou sem
    # `refresh`, vem a lista nova do Warcraft Logs (log ao vivo).
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    assert len(client.post("/reports/resolve", json=LINK).json()["fights"]) == 4

    wcl.report["fights"].append(nekzali(5, 1_300_000, 1_450_000))
    now[0] = 120
    response = client.post("/reports/resolve", json=LINK | body)

    assert [f["id"] for f in response.json()["fights"]] == [1, 2, 3, 4, 5]
    assert wcl.calls == ["ReportFights", "ReportFights"]


def test_resolve_right_after_a_fetch_uses_the_cache(client):
    # Cliques repetidos ou dois magos da raide colando o mesmo link: sem gastar pontos.
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    first = client.post("/reports/resolve", json=LINK).json()

    now[0] = REFRESH_MIN_INTERVAL_S - 1
    again = client.post("/reports/resolve", json=LINK).json()
    now[0] = REFRESH_MIN_INTERVAL_S + 1
    client.post("/reports/resolve", json=LINK)

    assert again["fetched_at"] == first["fetched_at"]
    assert wcl.calls == ["ReportFights", "ReportFights"]


def test_failed_resolve_shows_the_error_and_keeps_the_list(client):
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    client.post("/reports/resolve", json=LINK)

    wcl.status = 503
    now[0] = 120
    response = client.post("/reports/resolve", json=LINK)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "wcl_unavailable"
    # A lista guardada continua valendo para a escolha da luta (Magos e análise).
    wcl.status = 200
    assert client.get("/reports/TESTE123/fights/2/players").status_code == 200
    assert wcl.calls == ["ReportFights", "ReportFights", "FightPlayers"]


def test_fight_in_progress_is_marked_and_not_clickable(client):
    wcl = FakeWcl()
    wcl.report["fights"].append(nekzali(5, 1_300_000, 1_320_000, inProgress=True))
    use_wcl(wcl, [0.0])

    fights = {f["id"]: f for f in client.post("/reports/resolve", json=LINK).json()["fights"]}
    response = client.get("/reports/TESTE123/fights/5/players")

    assert fights[5]["in_progress"] is True
    assert fights[5]["supported"] is False
    assert fights[5]["unsupported_reason"] == IN_PROGRESS_REASON
    assert fights[2]["in_progress"] is False
    # Menos de 60 s até agora, mas o motivo é estar subindo, não ser curta.
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "unsupported_fight", "message": IN_PROGRESS_REASON}


# --- Pré-busca dos eventos -----------------------------------------------------------


def prefetch(client, fight_id: int = 2, actor_id: int = 10, code: str = "TESTE123"):
    return client.post(f"/reports/{code}/fights/{fight_id}/prefetch", json={"actor_id": actor_id})


def test_prefetch_answers_202_without_waiting_the_download(client):
    wcl = FakeWcl()
    wcl.gate = threading.Event()
    source = wcl.source()
    app.dependency_overrides[get_report_source] = lambda: source

    # A busca fica parada no gate: se a rota esperasse por ela, o teste travaria aqui.
    first = prefetch(client)
    assert wcl.fetching.wait(timeout=5)
    second = prefetch(client)
    wcl.gate.set()
    shutdown_prefetch()

    assert (first.status_code, first.json()) == (202, {"status": "started"})
    assert (second.status_code, second.json()) == (202, {"status": "running"})
    assert prefetch(client).json() == {"status": "ready"}
    # O que o motor vai ler já está no cache: nada de nova busca.
    calls = len(wcl.calls)
    assert source.get_fight_data("TESTE123", 2, 10)["player"]["actor"]["id"] == 10
    assert len(wcl.calls) == calls
    assert wcl.count("FightMeta") == 1


def test_prefetch_of_the_sample_fight_is_ready(client):
    response = prefetch(client, 34, 455, "XhrmBaYkGCAQjH2D")

    assert (response.status_code, response.json()) == (202, {"status": "ready"})


@pytest.mark.parametrize(
    ("fight_id", "actor_id", "status", "code"),
    [
        (34, 999, 422, "no_arcane_mage"),
        (33, 455, 422, "fight_too_short"),
        (41, 455, 422, "unsupported_fight"),
        (999, 455, 404, "fight_not_found"),
    ],
)
def test_prefetch_errors_are_the_same_of_the_players_route(
    client, fight_id, actor_id, status, code
):
    response = prefetch(client, fight_id, actor_id, "XhrmBaYkGCAQjH2D")

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_prefetch_of_unknown_report(client):
    response = prefetch(client, 34, 455, "OutroRelatorio1")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "report_not_available"


def test_prefetch_of_a_fire_mage_is_no_arcane_mage(client):
    wcl = FakeWcl()
    use_wcl(wcl, [0.0])

    response = prefetch(client, 2, 11)  # o 11 jogou Fogo

    assert response.json()["detail"]["code"] == "no_arcane_mage"
    assert wcl.count("FightMeta") == 0


def test_prefetch_with_wcl_down_is_wcl_unavailable(client):
    app.dependency_overrides[get_report_source] = DownSource

    response = prefetch(client)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "wcl_unavailable"


def test_fight_players_from_wcl_come_once_per_fight(client):
    wcl = FakeWcl()
    use_wcl(wcl, [0.0])

    for _ in range(2):
        response = client.get("/reports/TESTE123/fights/2/players")
        assert [p["actor_id"] for p in response.json()["players"]] == [10, 13]

    assert wcl.calls == ["ReportFights", "FightPlayers"]


class DownSource:
    """Fonte com o Warcraft Logs fora do ar (limite de pontos, 5xx, rede ou credenciais)."""

    def get_report(self, code: str, refresh: bool = False):
        raise SourceUnavailableError(code)

    def get_fight_players(self, code: str, fight_id: int):
        raise SourceUnavailableError(code)


def test_resolve_with_wcl_down_is_not_report_not_available(client):
    app.dependency_overrides[get_report_source] = DownSource

    response = client.post(
        "/reports/resolve", json={"url": "https://www.warcraftlogs.com/reports/OutroRelatorio1"}
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "wcl_unavailable"
    assert "público" not in detail["message"]


def test_fight_players_with_wcl_down_is_wcl_unavailable(client):
    wcl = FakeWcl()
    use_wcl(wcl, [0.0])
    client.post("/reports/resolve", json=LINK)  # lista já no cache

    wcl.status = 503
    response = client.get("/reports/TESTE123/fights/2/players")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "wcl_unavailable"
