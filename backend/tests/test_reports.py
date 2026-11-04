import threading

import pytest
from conftest import ANALYSIS
from fastapi import Request
from test_sources import (
    FakeWcl,
    fake_client,
    nekzali,
    now_ms,
    report_body,
    wait_prefetch,
)

from app.api.reports import (
    ARCHIVED_MESSAGE,
    CLASSIC_LINK_MESSAGE,
    FIGHT_NOT_FOUND_MESSAGE,
    INVALID_LINK_MESSAGE,
    NO_ARCANE_MAGE_MESSAGE,
    PREFETCH_LIMIT_MESSAGE,
    request_client,
)
from app.main import app
from app.models import User
from app.schemas import FIGHT_REASON_MESSAGES
from app.services.links import parse_report_code
from app.services.sources import (
    LIVE_WINDOW_S,
    QUERY_LIMIT,
    REFRESH_MIN_INTERVAL_S,
    WCL_COOLDOWN_S,
    ClientLimiter,
    FightNotFoundError,
    PlayerNotFoundError,
    ReportCache,
    SourceUnavailableError,
    WclReportSource,
    get_report_source,
)
from app.services.tops import get_tops_source
from app.wcl.client import CONFIG_MESSAGE, QUERY_MESSAGE

SAMPLE_LINK = "https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=34"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.warcraftlogs.com/reports/AbC123",  # T01 (entrada do item 10)
        "https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=34&type=damage-done",
        "warcraftlogs.com/reports/XhrmBaYkGCAQjH2D",
        "  https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D/  ",
        "https://de.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D",  # site em outro idioma
        "https://ko.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=34",
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
        "https://classic.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D",
        "https://outro.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D",
        "",
    ],
)
def test_t02_link_validator_rejects_other_links(url):
    assert parse_report_code(url) is None


@pytest.mark.parametrize("sub", ["classic", "sod", "fresh", "vanilla", "era"])
def test_classic_link_says_it_is_classic(client, sub):
    url = f"https://{sub}.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=3"

    response = client.post("/reports/resolve", json={"url": url})

    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "invalid_link", "message": CLASSIC_LINK_MESSAGE}


@pytest.mark.parametrize(
    "url", ["https://outro.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D", "https://google.com"]
)
def test_other_links_keep_the_invalid_link_message(client, url):
    response = client.post("/reports/resolve", json={"url": url})

    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "invalid_link", "message": INVALID_LINK_MESSAGE}


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
    assert fights[41]["unsupported_code"] == "unsupported_boss"
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
    source = wcl.source(clock=now)
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


def test_failed_resolve_brings_the_cached_list_as_stale(client):
    # WCL fora do ar ao colar de novo um link já aberto: a tela segue com a lista guardada.
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    first = client.post("/reports/resolve", json=LINK).json()

    wcl.status = 503
    now[0] = 120
    response = client.post("/reports/resolve", json=LINK)

    body = response.json()
    assert response.status_code == 200
    assert (first["stale"], first["stale_message"]) == (False, None)
    assert body["stale"] is True
    assert "fora do ar" in body["stale_message"]
    assert body["fetched_at"] == first["fetched_at"]
    assert body["fights"] == first["fights"]
    # A lista guardada continua valendo para a escolha da luta (Magos e análise), passada a
    # pausa depois da falha.
    wcl.status = 200
    now[0] += WCL_COOLDOWN_S
    assert client.get("/reports/TESTE123/fights/2/players").status_code == 200
    assert wcl.calls == ["ReportFights", "ReportFights", "FightPlayers"]


def test_new_fight_with_wcl_down_is_not_fight_not_found(client):
    # A luta pedida não está na lista guardada e a busca nova falhou: não dá para dizer que
    # ela não existe.
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    client.post("/reports/resolve", json=LINK)

    wcl.status = 503
    now[0] = 120
    response = client.get("/reports/TESTE123/fights/5/players")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "wcl_unavailable"


def test_failed_resolve_without_cached_list_is_503(client):
    use_wcl(FakeWcl(status=429), [0.0])

    response = client.post("/reports/resolve", json=LINK)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "wcl_unavailable"


def test_broken_query_is_unexpected_error_not_wcl_down(client):
    # Bug nosso: "Tentar de novo" não resolve, então não sai como Warcraft Logs fora do ar.
    broken = {"errors": [{"message": 'Cannot query field "x" on type "Report".'}]}
    source = WclReportSource(
        client_factory=lambda: fake_client(broken), cache=ReportCache(), players=ReportCache()
    )
    app.dependency_overrides[get_report_source] = lambda: source

    response = client.post("/reports/resolve", json=LINK)

    assert response.status_code == 500
    assert response.json()["detail"] == {"code": "unexpected_error", "message": QUERY_MESSAGE}


def test_other_boss_still_uploading_is_not_marked_as_uploading(client):
    wcl = FakeWcl()
    wcl.report["fights"].append(
        {"id": 5, "encounterID": 9999, "name": "Outro Chefe", "difficulty": 5, "kill": False,
         "startTime": 1_300_000, "endTime": 1_320_000, "inProgress": True}
    )  # fmt: skip
    use_wcl(wcl, [0.0])

    fights = {f["id"]: f for f in client.post("/reports/resolve", json=LINK).json()["fights"]}
    response = client.get("/reports/TESTE123/fights/5/players")

    assert fights[5]["in_progress"] is False
    assert fights[5]["unsupported_code"] == "unsupported_boss"
    assert fights[5]["unsupported_reason"] == FIGHT_REASON_MESSAGES["unsupported_boss"]
    # 20 s até agora, mas o motivo é o chefe, não a luta curta.
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "unsupported_fight",
        "message": FIGHT_REASON_MESSAGES["unsupported_boss"],
    }


def test_fight_in_progress_is_marked_and_not_clickable(client):
    wcl = FakeWcl()
    wcl.report["fights"].append(nekzali(5, 1_300_000, 1_320_000, inProgress=True))
    use_wcl(wcl, [0.0])

    fights = {f["id"]: f for f in client.post("/reports/resolve", json=LINK).json()["fights"]}
    response = client.get("/reports/TESTE123/fights/5/players")

    assert fights[5]["in_progress"] is True
    assert fights[5]["supported"] is False
    assert fights[5]["unsupported_code"] == "in_progress"
    assert fights[5]["unsupported_reason"] == FIGHT_REASON_MESSAGES["in_progress"]
    assert fights[2]["in_progress"] is False
    # Menos de 60 s até agora, mas o motivo é estar subindo, não ser curta.
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "unsupported_fight",
        "message": FIGHT_REASON_MESSAGES["in_progress"],
    }


def test_fight_reason_logic_does_not_depend_on_the_text(client, monkeypatch):
    # A rota decide pelo código do motivo: trocar o texto não muda o erro, só a mensagem.
    for code in ("short", "unsupported_boss", "in_progress"):
        monkeypatch.setitem(FIGHT_REASON_MESSAGES, code, f"texto trocado ({code})")
    wcl = FakeWcl()
    wcl.report["fights"].append(nekzali(5, 1_300_000, 1_320_000, inProgress=True))
    use_wcl(wcl, [0.0])
    client.post("/reports/resolve", json=LINK)

    # Luta 1: curta; luta 3: outro chefe; luta 5: subindo (lista recém-buscada).
    short = client.get("/reports/TESTE123/fights/1/players")
    boss = client.get("/reports/TESTE123/fights/3/players")
    uploading = client.get("/reports/TESTE123/fights/5/players")

    assert (short.status_code, short.json()["detail"]["code"]) == (422, "fight_too_short")
    assert boss.status_code == 422
    assert boss.json()["detail"] == {
        "code": "unsupported_fight",
        "message": "texto trocado (unsupported_boss)",
    }
    assert uploading.status_code == 422
    assert uploading.json()["detail"] == {
        "code": "unsupported_fight",
        "message": "texto trocado (in_progress)",
    }


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
    wait_prefetch()

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


class RecordingTops:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple] = []
        self.error = error

    def prefetch_tops(self, encounter_id, difficulty, item_level, own):
        self.calls.append((encounter_id, difficulty, item_level, own))
        if self.error is not None:
            raise self.error


def test_prefetch_also_asks_for_the_bracket_tops(client):
    tops = RecordingTops()
    app.dependency_overrides[get_tops_source] = lambda: tops

    response = prefetch(client, 34, 455, "XhrmBaYkGCAQjH2D")

    assert response.status_code == 202
    assert tops.calls == [(3470, 5, 327, ("XhrmBaYkGCAQjH2D", 34, "Harmonist"))]


def test_prefetch_tops_failure_does_not_change_the_answer(client):
    app.dependency_overrides[get_tops_source] = lambda: RecordingTops(RuntimeError("bug"))

    response = prefetch(client, 34, 455, "XhrmBaYkGCAQjH2D")

    assert (response.status_code, response.json()) == (202, {"status": "ready"})


def test_prefetch_limit_per_client(client, auth_headers):
    # Limite de 1 para o teste: o anônimo (IP) estoura, a conta logada tem o próprio limite.
    wcl = FakeWcl()
    source = wcl.source(limiter=ClientLimiter(max_calls=1))
    app.dependency_overrides[get_report_source] = lambda: source

    first = prefetch(client, 2, 10)
    blocked = prefetch(client, 2, 13)
    logged = client.post(
        "/reports/TESTE123/fights/2/prefetch", json={"actor_id": 13}, headers=auth_headers
    )
    wait_prefetch()

    assert first.json() == {"status": "started"}
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == {"code": "prefetch_limit", "message": PREFETCH_LIMIT_MESSAGE}
    assert logged.status_code == 202
    # Do cache não conta: o anônimo, já no limite, ainda recebe "ready".
    assert prefetch(client, 2, 10).json() == {"status": "ready"}


def test_prefetch_with_no_analyses_left_is_plan_limit(client, auth_headers):
    # Quem não vai poder analisar não gasta pontos do Warcraft Logs com a pré-busca.
    for _ in range(5):
        assert client.post("/analyses", json=ANALYSIS, headers=auth_headers).status_code == 201

    response = client.post(
        "/reports/XhrmBaYkGCAQjH2D/fights/34/prefetch", json={"actor_id": 455}, headers=auth_headers
    )
    blocked = client.post("/analyses", json=ANALYSIS, headers=auth_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == blocked.json()["detail"]
    assert response.json()["detail"]["code"] == "plan_limit"
    # Sem login não há contagem.
    assert prefetch(client, 34, 455, "XhrmBaYkGCAQjH2D").status_code == 202


def test_prefetch_with_an_expired_token_is_anonymous(client):
    # Login opcional: token inválido vale como sem login, como no /analyses.
    response = client.post(
        "/reports/XhrmBaYkGCAQjH2D/fights/34/prefetch",
        json={"actor_id": 455},
        headers={"Authorization": "Bearer token-vencido"},
    )

    assert response.status_code == 202


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

    def get_report(self, code: str, refresh: bool = False, client=None):
        raise SourceUnavailableError(code)

    def get_fight_players(self, code: str, fight_id: int, client=None):
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


# --- Código do erro na lista guardada, pausa depois da falha e teto da pré-busca -------


def test_stale_list_brings_the_error_code(client):
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    assert client.post("/reports/resolve", json=LINK).json()["stale_code"] is None

    wcl.status = 403  # credencial recusada: erro nosso
    now[0] = 120
    body = client.post("/reports/resolve", json=LINK).json()

    assert (body["stale"], body["stale_code"]) == (True, "unexpected_error")
    assert body["stale_message"] == CONFIG_MESSAGE


def test_new_fight_with_a_config_error_keeps_status_and_code(client):
    # Lista guardada por erro nosso: a luta nova não sai como "Warcraft Logs fora do ar".
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    client.post("/reports/resolve", json=LINK)

    wcl.status = 403
    now[0] = 120
    response = client.get("/reports/TESTE123/fights/5/players")

    assert response.status_code == 500
    assert response.json()["detail"] == {"code": "unexpected_error", "message": CONFIG_MESSAGE}


def test_tabs_refreshing_during_the_pause_do_not_call_the_wcl(client):
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    client.post("/reports/resolve", json=LINK)
    wcl.status, wcl.headers = 429, {"retry-after": "60"}
    now[0] = 120

    bodies = [client.post("/reports/resolve", json=LINK | {"refresh": True}).json()]
    now[0] = 150
    bodies += [client.post("/reports/resolve", json=LINK).json() for _ in range(3)]
    missing = client.get("/reports/TESTE123/fights/5/players")

    assert all(b["stale"] and b["stale_code"] == "wcl_unavailable" for b in bodies)
    assert "limitando os pedidos" in bodies[-1]["stale_message"]
    assert (missing.status_code, missing.json()["detail"]["code"]) == (503, "wcl_unavailable")
    assert wcl.calls == ["ReportFights", "ReportFights"]


def test_prefetch_during_the_pause_is_wcl_unavailable(client):
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    client.get("/reports/TESTE123/fights/2/players")  # lista e Magos no cache
    wcl.status = 503
    now[0] = 120
    client.post("/reports/resolve", json=LINK)  # falha: começa a pausa

    response = prefetch(client)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "wcl_unavailable"
    assert wcl.count("FightMeta") == 0


def test_prefetch_global_cap(client, auth_headers):
    # O teto do processo vale para todos: a conta logada não escapa dele.
    wcl = FakeWcl()
    source = wcl.source(limiter=ClientLimiter(global_max_calls=1))
    app.dependency_overrides[get_report_source] = lambda: source

    first = prefetch(client, 2, 10)
    blocked = client.post(
        "/reports/TESTE123/fights/2/prefetch", json={"actor_id": 13}, headers=auth_headers
    )
    wait_prefetch()

    assert first.json() == {"status": "started"}
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == {"code": "prefetch_limit", "message": PREFETCH_LIMIT_MESSAGE}


def request_from(host: str | None) -> Request:
    return Request({"type": "http", "client": None if host is None else (host, 50000)})


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("203.0.113.7", "ip:203.0.113.7"),
        ("2001:db8:1:2::5", "ip:2001:db8:1:2::/64"),
        ("2001:db8:1:2:ffff:ffff:ffff:ffff", "ip:2001:db8:1:2::/64"),  # mesma casa
        ("2001:db8:1:3::5", "ip:2001:db8:1:3::/64"),  # outra rede
        ("::ffff:203.0.113.7", "ip:203.0.113.7"),  # IPv4 escrito em IPv6
        ("testclient", "ip:testclient"),  # não é IP
        (None, None),
    ],
)
def test_request_client_groups_ipv6_by_64(host, expected):
    assert request_client(request_from(host), None) == expected


def test_request_client_prefers_the_account():
    user = User(id="u7", email="jogador@exemplo.com", password_hash="x")

    assert request_client(request_from("2001:db8::1"), user) == "user:u7"


# --- Luta que estava subindo na lista guardada ------------------------------------------


def test_fight_that_finished_after_the_cached_list_is_accepted(client):
    # A lista guardada é de quando a luta subia; a busca nova já a traz terminada.
    now = [0.0]
    wcl = FakeWcl()
    wcl.report["fights"].append(nekzali(5, 1_300_000, 1_320_000, inProgress=True))
    use_wcl(wcl, now)
    fights = {f["id"]: f for f in client.post("/reports/resolve", json=LINK).json()["fights"]}
    assert fights[5]["in_progress"] is True

    wcl.report["fights"][-1] = nekzali(5, 1_300_000, 1_700_000, kill=True)
    now[0] = REFRESH_MIN_INTERVAL_S + 1
    response = client.get("/reports/TESTE123/fights/5/players")

    assert response.status_code == 200
    assert wcl.calls == ["ReportFights", "ReportFights", "FightPlayers"]


def test_fight_still_uploading_is_refused_after_one_new_search(client):
    now = [0.0]
    wcl = FakeWcl()
    wcl.report["fights"].append(nekzali(5, 1_300_000, 1_320_000, inProgress=True))
    use_wcl(wcl, now)
    client.post("/reports/resolve", json=LINK)

    now[0] = REFRESH_MIN_INTERVAL_S + 1
    response = client.get("/reports/TESTE123/fights/5/players")

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "unsupported_fight",
        "message": FIGHT_REASON_MESSAGES["in_progress"],
    }
    assert wcl.calls == ["ReportFights", "ReportFights"]  # uma busca nova só


def test_fight_of_a_paused_upload_is_refused(client):
    # O uploader parou há mais de 10 min: a luta não fica "subindo" para sempre.
    now = [0.0]
    wcl = FakeWcl()
    wcl.report["fights"].append(nekzali(5, 1_300_000, 1_320_000, inProgress=True))
    wcl.end_time = now_ms() - (LIVE_WINDOW_S + 60) * 1000
    use_wcl(wcl, now)

    body = client.post("/reports/resolve", json=LINK).json()
    fight = {f["id"]: f for f in body["fights"]}[5]
    now[0] = REFRESH_MIN_INTERVAL_S + 1
    response = client.get("/reports/TESTE123/fights/5/players")

    assert body["live"] is False
    assert (fight["in_progress"], fight["upload_paused"], fight["supported"]) == (
        False,
        True,
        False,
    )
    assert fight["unsupported_code"] == "upload_paused"
    assert fight["unsupported_reason"] == FIGHT_REASON_MESSAGES["upload_paused"]
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "unsupported_fight",
        "message": FIGHT_REASON_MESSAGES["upload_paused"],
    }
    assert wcl.calls == ["ReportFights", "ReportFights"]


def test_resolve_of_a_live_log_says_it_is_live(client):
    use_wcl(FakeWcl(), [0.0])

    assert client.post("/reports/resolve", json=LINK).json()["live"] is True


# --- Limite de consultas por cliente ----------------------------------------------------


def spend_resolves(client, now: list[float], headers: dict | None = None) -> None:
    for _ in range(QUERY_LIMIT):
        now[0] += REFRESH_MIN_INTERVAL_S
        assert client.post("/reports/resolve", json=LINK, headers=headers).status_code == 200


def test_query_over_the_limit_is_429(client):
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    spend_resolves(client, now)

    response = client.get("/reports/TESTE123/fights/2/players")

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["code"] == "query_limit"
    assert detail["message"].startswith("Você fez muitas consultas ao Warcraft Logs")
    assert detail["message"].endswith("min.")
    assert wcl.count("FightPlayers") == 0


def test_resolve_over_the_limit_brings_the_cached_list_as_stale(client):
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    spend_resolves(client, now)

    now[0] += REFRESH_MIN_INTERVAL_S
    response = client.post("/reports/resolve", json=LINK)

    body = response.json()
    assert response.status_code == 200
    assert (body["stale"], body["stale_code"]) == (True, "query_limit")
    assert wcl.count("ReportFights") == QUERY_LIMIT


def test_resolve_over_the_limit_without_cached_list_is_429(client):
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    spend_resolves(client, now)

    response = client.post(
        "/reports/resolve", json={"url": "https://www.warcraftlogs.com/reports/OUTRO1234"}
    )

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "query_limit"


def test_prefetch_route_counts_its_queries_in_the_limit(client):
    # A pré-busca direto, sem a tela ter aberto a luta, também gasta a lista e os Magos.
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    spend_resolves(client, now)

    response = client.post("/reports/TESTE123/fights/2/prefetch", json={"actor_id": 10})

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "query_limit"
    assert wcl.count("FightPlayers") == 0


def test_query_limit_is_per_account(client, auth_headers):
    # Sem login conta o IP; com login, a conta: um não gasta o do outro.
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    spend_resolves(client, now)

    response = client.get("/reports/TESTE123/fights/2/players", headers=auth_headers)

    assert response.status_code == 200


def test_cached_answers_do_not_count_in_the_query_limit(client):
    now = [0.0]
    wcl = FakeWcl()
    use_wcl(wcl, now)
    for _ in range(QUERY_LIMIT + 5):
        assert client.post("/reports/resolve", json=LINK).status_code == 200  # trava de 8 s
        assert client.get("/reports/TESTE123/fights/2/players").status_code == 200

    assert wcl.calls == ["ReportFights", "FightPlayers"]


def test_sample_mode_does_not_count_in_the_query_limit(client):
    for _ in range(QUERY_LIMIT + 5):
        assert client.post("/reports/resolve", json={"url": SAMPLE_LINK}).status_code == 200


# --- Erros mapeados certo -------------------------------------------------------------


class FightGoneSource:
    """A lista tem a luta 2, mas a consulta dos Magos diz outra coisa."""

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.wcl = FakeWcl()
        self.source = self.wcl.source()

    def get_report(self, code: str, refresh: bool = False, client=None):
        return self.source.get_report(code, refresh=refresh, client=client)

    def get_fight_players(self, code: str, fight_id: int, client=None):
        raise self.error


@pytest.mark.parametrize(
    ("error", "status", "code", "message"),
    [
        (FightNotFoundError("TESTE123"), 404, "fight_not_found", FIGHT_NOT_FOUND_MESSAGE),
        (PlayerNotFoundError("TESTE123"), 422, "no_arcane_mage", NO_ARCANE_MAGE_MESSAGE),
    ],
)
def test_missing_fight_or_player_is_not_report_not_available(client, error, status, code, message):
    source = FightGoneSource(error)
    app.dependency_overrides[get_report_source] = lambda: source

    response = client.get("/reports/TESTE123/fights/2/players")

    assert response.status_code == status
    assert response.json()["detail"] == {"code": code, "message": message}


def test_fight_missing_in_the_wcl_players_query_is_fight_not_found(client):
    # A lista guardada tem a luta, mas o WCL não a acha na consulta dos Magos.
    wcl = FakeWcl()
    use_wcl(wcl, [0.0])
    client.post("/reports/resolve", json=LINK)
    wcl.report["fights"] = [f for f in wcl.report["fights"] if f["id"] != 2]

    response = client.get("/reports/TESTE123/fights/2/players")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "fight_not_found"


def test_archived_report_says_it_was_archived(client):
    body = report_body(
        None, [{"message": "This report is archived.", "path": ["reportData", "report"]}]
    )
    source = WclReportSource(
        client_factory=lambda: fake_client(body), cache=ReportCache(), players=ReportCache()
    )
    app.dependency_overrides[get_report_source] = lambda: source

    response = client.post("/reports/resolve", json=LINK)

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "report_not_available",
        "message": ARCHIVED_MESSAGE,
    }


def test_old_clients_sending_refresh_still_work(client):
    response = client.post("/reports/resolve", json={"url": SAMPLE_LINK, "refresh": True})

    assert response.status_code == 200
