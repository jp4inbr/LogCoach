"""De quem é cada erro do Warcraft Logs e que mensagem o usuário vê (item 12.8).

Os corpos imitam o que a API real devolveu em 28/10/2026 (report inexistente, erro de
sintaxe, token inválido, credencial errada) e o que o Cloudflare manda na frente dela.
"""

import logging
import threading
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from app.wcl.client import (
    API_URL,
    BLOCKED_MESSAGE,
    CONFIG_MESSAGE,
    NETWORK_MESSAGE,
    QUERY_MESSAGE,
    TIMEOUT_MESSAGE,
    TOKEN_URL,
    UNAVAILABLE_MESSAGE,
    UNEXPECTED_MESSAGE,
    WclClient,
    WclError,
    WclUnavailableError,
    rate_limit_message,
)

REPORT_QUERY = "query($c:String!){ reportData { report(code:$c){ code title } } }"

# Como a API respondeu de verdade (só o essencial).
NOT_FOUND_BODY = {
    "errors": [
        {
            "message": "This report does not exist.",
            "locations": [{"line": 1, "column": 33}],
            "path": ["reportData", "report"],
        }
    ],
    "data": {"reportData": {"report": None}},
}
NOT_FOUND_HTML = (
    '<!DOCTYPE html>\n<html lang="en">\n<head><title>Not Found</title></head>\n'
    "<body>Not Found</body></html>"
)
CLOUDFLARE_CHALLENGE = (
    "<!DOCTYPE html><html><head><title>Just a moment...</title></head>"
    "<body>Checking your browser before accessing warcraftlogs.com</body></html>"
)
CLOUDFLARE_52X = (
    "<!DOCTYPE html><html><head><title>warcraftlogs.com | 522: Connection timed out"
    "</title></head><body>Cloudflare</body></html>"
)
HTML = {"content-type": "text/html; charset=UTF-8"}


def token_response(token: str = "tok") -> httpx.Response:
    # O WCL dá um token de ~360 dias (expires_in 31104000).
    return httpx.Response(
        200, json={"token_type": "Bearer", "expires_in": 31104000, "access_token": token}
    )


def client_for(api, token=None, **kwargs) -> WclClient:
    """`api` e `token` são respostas fixas ou funções request → resposta."""

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            if token is None:
                return token_response()
            return token(request) if callable(token) else token
        assert str(request.url) == API_URL
        return api(request) if callable(api) else api

    return WclClient("id", "secret", transport=httpx.MockTransport(handler), **kwargs)


def raised(client: WclClient) -> WclError:
    with pytest.raises(WclError) as info:
        client.query(REPORT_QUERY, {"c": "AAAAAAAAAAAAAAAA"})
    return info.value


def user_message(client: WclClient) -> str:
    error = raised(client)
    assert isinstance(error, WclUnavailableError), error
    return error.user_message


# --- Do report: continua WclError puro (vira report_not_available na fonte) ----------


@pytest.mark.parametrize(
    "message",
    ["This report does not exist.", "You do not have permission to view this report."],
)
def test_missing_or_private_report_is_report_error(message):
    body = {**NOT_FOUND_BODY, "errors": [{**NOT_FOUND_BODY["errors"][0], "message": message}]}

    error = raised(client_for(httpx.Response(200, json=body)))

    assert not isinstance(error, WclUnavailableError)
    assert message in str(error)


@pytest.mark.parametrize(
    "error",
    [
        # Texto diferente, mas no campo do report: é o report.
        {"message": "Report is archived.", "path": ["reportData", "report"]},
        # Sem `path`, mas com `report: null` na resposta: também é o report.
        {"message": "Sem permissão"},
    ],
)
def test_unknown_message_with_null_report_is_report_error(error):
    body = {"errors": [error], "data": {"reportData": {"report": None}}}

    assert not isinstance(raised(client_for(httpx.Response(200, json=body))), WclUnavailableError)


def test_internal_error_with_null_report_is_still_outage():
    body = {
        "errors": [{"message": "Internal server error"}],
        "data": {"reportData": {"report": None}},
    }

    assert user_message(client_for(httpx.Response(200, json=body))) == UNAVAILABLE_MESSAGE


def test_malformed_code_is_report_error():
    # Observado: código com caracteres inválidos dá o mesmo "does not exist".
    assert not isinstance(
        raised(client_for(httpx.Response(200, json=NOT_FOUND_BODY))), WclUnavailableError
    )


# --- Do Warcraft Logs -----------------------------------------------------------------


def test_internal_graphql_error_is_outage():
    body = {"errors": [{"message": "Internal server error"}], "data": None}

    assert user_message(client_for(httpx.Response(200, json=body))) == UNAVAILABLE_MESSAGE


def test_rate_limit_inside_graphql_is_rate_limit():
    body = {"errors": [{"message": "You have exceeded your rate limit."}]}

    message = user_message(client_for(httpx.Response(200, json=body)))

    assert "limitando" in message


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"retry-after": "120"}, "daqui a uns 2 minutos"),
        ({"retry-after": "30"}, "daqui a uns 1 minuto"),
        ({}, "em até 1 hora"),
    ],
)
def test_429_says_when_to_try_again(headers, expected):
    response = httpx.Response(429, headers=headers, json={"error": "Too Many Requests"})

    message = user_message(client_for(response))

    assert "limitando os pedidos" in message
    assert expected in message


def test_429_with_http_date():
    when = format_datetime(datetime.now(UTC) + timedelta(minutes=10), usegmt=True)
    response = httpx.Response(429, headers={"retry-after": when}, text="Too Many Requests")

    message = user_message(client_for(response))

    assert "10 minutos" in message or "9 minutos" in message


@pytest.mark.parametrize(
    ("response", "rate_limited", "retry_after_s"),
    [
        (httpx.Response(429, headers={"retry-after": "120"}, json={}), True, 120),
        (httpx.Response(429, json={}), True, None),
        # Manutenção com Retry-After: não é limite, mas o tempo vale para a pausa da fonte.
        (httpx.Response(503, headers={"retry-after": "300"}, json={}), False, 300),
        (httpx.Response(502, json={}), False, None),
        (httpx.Response(200, json={"errors": [{"message": "Rate limit exceeded"}]}), True, None),
    ],
)
def test_unavailable_error_carries_the_wait(response, rate_limited, retry_after_s):
    error = raised(client_for(response))

    assert isinstance(error, WclUnavailableError)
    assert (error.rate_limited, error.retry_after_s) == (rate_limited, retry_after_s)


def test_rate_limit_message_without_time_does_not_promise_minutes():
    assert "1 hora" in rate_limit_message(None)
    assert rate_limit_message(61).endswith("uns 2 minutos.")


def test_cloudflare_1015_is_rate_limit():
    # Rate limit do Cloudflare: 429 com página HTML.
    response = httpx.Response(429, headers=HTML, text="<html>Error 1015 You are being rate limited")

    assert "limitando" in user_message(client_for(response))


@pytest.mark.parametrize("status", [500, 502, 503, 504, 520, 521, 522, 523, 524])
def test_server_and_cloudflare_5xx_are_outage(status):
    response = httpx.Response(status, headers=HTML, text=CLOUDFLARE_52X)

    assert user_message(client_for(response)) == UNAVAILABLE_MESSAGE


def test_maintenance_page_with_200_is_outage():
    response = httpx.Response(200, headers=HTML, text="<html>Down for maintenance</html>")

    assert user_message(client_for(response)) == UNAVAILABLE_MESSAGE


def test_cloudflare_challenge_is_blocked():
    response = httpx.Response(
        403, headers={**HTML, "cf-mitigated": "challenge"}, text=CLOUDFLARE_CHALLENGE
    )

    assert user_message(client_for(response)) == BLOCKED_MESSAGE


def test_cloudflare_block_on_token_is_blocked():
    token = httpx.Response(403, headers=HTML, text=CLOUDFLARE_CHALLENGE)

    assert user_message(client_for(httpx.Response(200, json={}), token=token)) == BLOCKED_MESSAGE


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ReadTimeout("demorou"), TIMEOUT_MESSAGE),
        (httpx.ConnectTimeout("demorou"), TIMEOUT_MESSAGE),
        (httpx.PoolTimeout("fila"), TIMEOUT_MESSAGE),
        (httpx.ConnectError("sem rede"), NETWORK_MESSAGE),
        (httpx.RemoteProtocolError("caiu no meio"), NETWORK_MESSAGE),
    ],
)
def test_network_errors_say_what_happened(error, expected):
    def api(request: httpx.Request) -> httpx.Response:
        raise error

    assert user_message(client_for(api)) == expected


def test_timeout_on_token_is_timeout():
    def token(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("token travou")

    assert user_message(client_for(httpx.Response(200, json={}), token=token)) == TIMEOUT_MESSAGE


# --- Nosso: configuração ----------------------------------------------------------------


def test_invalid_token_404_html_gets_new_token_and_retries():
    # Observado: token inválido na API dá 404 com página HTML, não 401.
    responses = iter([httpx.Response(404, headers=HTML, text=NOT_FOUND_HTML)])
    tokens = iter(["velho", "novo"])

    def api(request: httpx.Request) -> httpx.Response:
        return next(responses, httpx.Response(200, json={"data": {"ok": 1}}))

    def token(request: httpx.Request) -> httpx.Response:
        return token_response(next(tokens))

    assert client_for(api, token=token).query("{ ok }") == {"ok": 1}


def test_token_refused_twice_is_config_error():
    response = httpx.Response(404, headers=HTML, text=NOT_FOUND_HTML)

    assert user_message(client_for(response)) == CONFIG_MESSAGE


@pytest.mark.parametrize("status", [400, 401])
def test_wrong_credentials_are_config_error(status, caplog):
    # Observado: 401 {"error":"invalid_client","error_description":"Client authentication failed"}
    token = httpx.Response(
        status,
        json={"error": "invalid_client", "error_description": "Client authentication failed"},
    )

    with caplog.at_level(logging.ERROR, logger="app.wcl.client"):
        message = user_message(client_for(httpx.Response(200, json={}), token=token))

    assert message == CONFIG_MESSAGE
    assert "invalid_client" in caplog.text


def test_missing_credentials_are_config_error(monkeypatch):
    from app.config import Settings

    empty = Settings(_env_file=None, wcl_client_id="", wcl_client_secret="")
    monkeypatch.setattr("app.wcl.client.get_settings", lambda: empty)

    with pytest.raises(WclUnavailableError) as info:
        WclClient.from_env()

    assert info.value.user_message == CONFIG_MESSAGE


def test_config_message_does_not_leak_details():
    assert "WCL_CLIENT" not in CONFIG_MESSAGE
    assert "LogCoach" in CONFIG_MESSAGE


# --- Não reconhecido: não fingir que sabe ------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        "Syntax Error: Unexpected )",
        'Cannot query field "friendlySpecs" on type "ReportFight".',
        'Unknown argument "foo" on field "fights" of type "Report".',
        'Variable "$fightID" of required type "Int!" was not provided.',
    ],
)
def test_broken_query_is_our_fault_and_logged(error, caplog):
    body = {"errors": [{"message": error, "locations": [{"line": 1, "column": 29}]}]}
    with caplog.at_level(logging.ERROR, logger="app.wcl.client"):
        message = user_message(client_for(httpx.Response(200, json=body)))

    assert message == QUERY_MESSAGE
    assert "nosso" in message and "Warcraft Logs respondeu" not in message
    assert error[:20] in caplog.text


def test_unknown_graphql_error_is_unexpected_and_logged(caplog):
    body = {"errors": [{"message": "Something new happened"}]}
    with caplog.at_level(logging.ERROR, logger="app.wcl.client"):
        message = user_message(client_for(httpx.Response(200, json=body)))

    assert message == UNEXPECTED_MESSAGE
    assert "Something new happened" in caplog.text


@pytest.mark.parametrize("status", [400, 404, 418])
def test_unknown_status_is_unexpected(status, caplog):
    response = httpx.Response(status, json={"message": "coisa nova"})

    with caplog.at_level(logging.ERROR, logger="app.wcl.client"):
        assert user_message(client_for(response)) == UNEXPECTED_MESSAGE
    assert "coisa nova" in caplog.text


@pytest.mark.parametrize("body", [{}, {"data": None}, {"errors": []}])
def test_response_without_data_is_unexpected_not_key_error(body):
    assert user_message(client_for(httpx.Response(200, json=body))) == UNEXPECTED_MESSAGE


def test_json_that_is_not_an_object_is_unexpected():
    assert user_message(client_for(httpx.Response(200, json=[1, 2]))) == UNEXPECTED_MESSAGE


def test_token_without_access_token_is_unexpected_not_key_error():
    token = httpx.Response(200, json={"token_type": "Bearer"})

    assert user_message(client_for(httpx.Response(200, json={}), token=token)) == UNEXPECTED_MESSAGE


def test_token_not_json_is_outage():
    token = httpx.Response(200, headers=HTML, text="<html>Bad gateway</html>")

    assert (
        user_message(client_for(httpx.Response(200, json={}), token=token)) == UNAVAILABLE_MESSAGE
    )


def test_token_without_expires_in_still_works():
    token = httpx.Response(200, json={"access_token": "tok"})

    assert client_for(httpx.Response(200, json={"data": {"ok": 1}}), token=token).query("{ ok }")


def test_events_on_missing_report_is_report_error():
    body = {"data": {"reportData": {"report": None}}}

    with pytest.raises(WclError) as info:
        client_for(httpx.Response(200, json=body)).events("X", 1, 0, 10, "Casts")

    assert not isinstance(info.value, WclUnavailableError)


# --- Tempos de espera -------------------------------------------------------------------


def test_token_and_queries_use_separate_timeouts():
    seen: dict[str, dict] = {}

    def token(request: httpx.Request) -> httpx.Response:
        seen["token"] = request.extensions["timeout"]
        return token_response()

    def api(request: httpx.Request) -> httpx.Response:
        seen["api"] = request.extensions["timeout"]
        return httpx.Response(200, json={"data": {}})

    client_for(api, token=token).query("{ a }")

    assert seen["token"]["connect"] == seen["api"]["connect"] == 5
    assert seen["token"]["read"] == 10
    # Consulta pequena: 10 s. As páginas de eventos (60 s) estão em test_wcl.py.
    assert seen["api"]["read"] == 10


def test_waiting_for_token_has_a_limit():
    # Outra thread está presa pedindo o token: quem chega não espera para sempre.
    client = client_for(httpx.Response(200, json={"data": {}}), token_wait_s=0.05)
    client._token_lock.acquire()
    try:
        assert user_message(client) == TIMEOUT_MESSAGE
    finally:
        client._token_lock.release()


def test_stuck_token_endpoint_does_not_queue_forever():
    # O 1º pedido do token trava; os outros desistem em `token_wait_s`, sem somar esperas.
    entered, release = threading.Event(), threading.Event()

    def token(request: httpx.Request) -> httpx.Response:
        entered.set()
        release.wait(2)
        return token_response()

    client = client_for(httpx.Response(200, json={"data": {}}), token=token, token_wait_s=0.1)
    first = threading.Thread(target=lambda: client.query("{ a }"))
    first.start()
    assert entered.wait(2)
    try:
        assert user_message(client) == TIMEOUT_MESSAGE
    finally:
        release.set()
        first.join()


# --- Código da API: do Warcraft Logs (503) ou nosso (500) ----------------------------


def error_code(client: WclClient) -> str:
    error = raised(client)
    assert isinstance(error, WclUnavailableError), error
    return error.error_code


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(429, json={}),
        httpx.Response(200, json={"errors": [{"message": "Internal server error"}]}),
    ],
)
def test_wcl_side_errors_are_wcl_unavailable(response):
    # Tentar de novo daqui a pouco resolve: a tela oferece "Tentar de novo".
    assert error_code(client_for(response)) == "wcl_unavailable"


def test_broken_query_is_unexpected_error():
    # Bug nosso: tentar de novo não resolve, então não sai como "Warcraft Logs fora do ar".
    body = {"errors": [{"message": 'Cannot query field "x" on type "Report".'}]}

    assert error_code(client_for(httpx.Response(200, json=body))) == "unexpected_error"


def test_config_error_is_unexpected_error():
    token = httpx.Response(401, json={"error": "invalid_client"})

    assert error_code(client_for(httpx.Response(200, json={}), token=token)) == "unexpected_error"


def test_unavailable_error_stays_compatible():
    # Quem já cria `WclUnavailableError(detail, user_message)` continua com o código do WCL.
    assert WclUnavailableError("x", "y").error_code == "wcl_unavailable"
    assert WclUnavailableError("x").user_message == UNAVAILABLE_MESSAGE
