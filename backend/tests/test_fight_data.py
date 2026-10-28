"""Eventos da luta do jogador: cache, single-flight e pré-busca (nada aqui acessa a internet).

As buscas "lentas" esperam um `threading.Event` que o teste libera; nenhum teste depende de
sleep, e o `fresh_wcl_state` desliga o executor da pré-busca no fim de cada um.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_sources import FakeWcl, fresh_wcl_state  # noqa: F401 (fixture autouse)

from app.services.sources import (
    SAMPLE_ACTOR_ID,
    SAMPLE_REPORT_CODE,
    FightDataNotAvailableError,
    FightDataStore,
    ReportNotAvailableError,
    SampleReportSource,
    SourceUnavailableError,
    shutdown_prefetch,
)

FIGHT = ("TESTE123", 2, 10)  # código, luta, ator (arcano_a do Norte)


def slow_wcl() -> FakeWcl:
    wcl = FakeWcl()
    wcl.gate = threading.Event()
    return wcl


def test_fight_data_comes_in_the_engine_format_and_once():
    wcl = FakeWcl()
    source = wcl.source()

    data = source.get_fight_data(*FIGHT)
    again = source.get_fight_data(*FIGHT)

    assert data["meta"]["fight"]["id"] == 2
    assert data["player"]["actor"]["id"] == 10
    assert [e["abilityGameID"] for e in data["events"]["casts"]] == [30451]
    assert again == data
    assert wcl.count("FightMeta") == 1
    events = wcl.count("Events")
    assert events == len(data["events"])  # uma página de cada tipo, só na primeira vez


def test_fight_data_is_a_copy():
    source = FakeWcl().source()

    source.get_fight_data(*FIGHT)["events"]["casts"].clear()

    assert len(source.get_fight_data(*FIGHT)["events"]["casts"]) == 1


def test_fight_data_is_per_player():
    wcl = FakeWcl()
    source = wcl.source()

    source.get_fight_data("TESTE123", 2, 10)
    other = source.get_fight_data("TESTE123", 2, 13)

    assert other["player"]["actor"]["id"] == 13
    assert wcl.count("FightMeta") == 2


def test_prefetch_answers_without_waiting_the_download():
    wcl = slow_wcl()
    source = wcl.source()

    # A busca fica parada no gate: se o prefetch esperasse por ela, o teste travaria aqui.
    assert source.prefetch(*FIGHT) == "started"
    assert wcl.fetching.wait(timeout=5)
    assert source.prefetch(*FIGHT) == "running"  # segunda chamada não baixa de novo

    wcl.gate.set()
    shutdown_prefetch()

    assert source.prefetch(*FIGHT) == "ready"
    assert wcl.count("FightMeta") == 1


def test_fight_data_after_prefetch_does_not_call_the_api():
    wcl = FakeWcl()
    source = wcl.source()
    source.prefetch(*FIGHT)
    shutdown_prefetch()  # espera a pré-busca terminar
    calls = len(wcl.calls)

    data = source.get_fight_data(*FIGHT)

    assert data["player"]["actor"]["id"] == 10
    assert len(wcl.calls) == calls


def test_fight_data_waits_for_the_running_prefetch():
    # Single-flight: clicou em analisar com a pré-busca ainda baixando. Espera a mesma busca.
    wcl = slow_wcl()
    source = wcl.source()
    assert source.prefetch(*FIGHT) == "started"
    assert wcl.fetching.wait(timeout=5)

    release = threading.Timer(0.05, wcl.gate.set)  # libera depois que o pedido já espera
    release.start()
    try:
        data = source.get_fight_data(*FIGHT)
    finally:
        release.cancel()
        wcl.gate.set()

    assert data["player"]["actor"]["id"] == 10
    assert wcl.count("FightMeta") == 1


def test_two_requests_at_the_same_time_download_once():
    wcl = slow_wcl()
    source = wcl.source()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(source.get_fight_data, *FIGHT)
        assert wcl.fetching.wait(timeout=5)
        second = pool.submit(source.get_fight_data, *FIGHT)
        wcl.gate.set()
        results = [first.result(timeout=5), second.result(timeout=5)]

    assert results[0] == results[1]
    assert wcl.count("FightMeta") == 1


def test_failed_prefetch_is_only_logged_and_not_cached(caplog):
    wcl = FakeWcl(status=503)
    source = wcl.source()

    with caplog.at_level(logging.WARNING, logger="app.services.sources"):
        assert source.prefetch(*FIGHT) == "started"
        shutdown_prefetch()
    assert "Pré-busca" in caplog.text

    # A API voltou: a próxima chamada tenta de novo (nada de erro guardado).
    wcl.status = 200
    assert source.prefetch(*FIGHT) == "started"
    shutdown_prefetch()
    assert source.prefetch(*FIGHT) == "ready"
    assert wcl.count("FightMeta") == 2


def test_failed_fight_data_raises_and_is_not_cached():
    wcl = FakeWcl(status=503)
    source = wcl.source()

    with pytest.raises(SourceUnavailableError):
        source.get_fight_data(*FIGHT)

    wcl.status = 200
    assert source.get_fight_data(*FIGHT)["player"]["actor"]["id"] == 10


def test_fight_missing_in_wcl_is_report_not_available():
    wcl = FakeWcl()
    wcl.report["fights"] = []

    with pytest.raises(ReportNotAvailableError):
        wcl.source().get_fight_data(*FIGHT)


def test_waiter_gets_the_error_of_the_running_fetch():
    store = FightDataStore()
    gate = threading.Event()
    started = threading.Event()
    calls: list[str] = []

    def failing():
        calls.append("busca")
        started.set()
        assert gate.wait(timeout=5)
        raise SourceUnavailableError("TESTE123")

    with ThreadPoolExecutor(max_workers=1) as pool:
        assert store.start("chave", failing, pool) == "started"
        assert started.wait(timeout=5)
        release = threading.Timer(0.05, gate.set)
        release.start()
        try:
            with pytest.raises(SourceUnavailableError):
                store.get("chave", lambda: pytest.fail("não pode baixar de novo"))
        finally:
            release.cancel()
            gate.set()

    assert calls == ["busca"]
    # Falha não fica no cache: o próximo pedido busca de novo.
    assert store.get("chave", lambda: ({"ok": True}, True)) == {"ok": True}


def test_store_keeps_only_the_newest_fights():
    store = FightDataStore()

    for n in range(12):
        store.get(n, lambda n=n: ({"luta": n}, True))

    assert store.get(0, lambda: ({"nova": True}, True)) == {"nova": True}
    assert store.get(11, lambda: pytest.fail("estava no cache")) == {"luta": 11}


def test_sample_fallback_is_not_kept():
    # Plano B do exemplo (valor que não pode ser guardado): o próximo pedido busca de novo.
    store = FightDataStore()
    calls: list[int] = []

    def sample():
        calls.append(1)
        return {"exemplo": True}, False

    store.get("chave", sample)
    store.get("chave", sample)

    assert len(calls) == 2


# --- Modo exemplo -------------------------------------------------------------------


def test_sample_fight_data_is_the_reference_fixture():
    data = SampleReportSource().get_fight_data(SAMPLE_REPORT_CODE, 34, SAMPLE_ACTOR_ID)

    assert data["meta"]["fight"]["id"] == 34
    assert data["player"]["actor"]["display_name"] == "Harmonist"
    assert data["events"]["casts"]


@pytest.mark.parametrize(("fight_id", "actor_id"), [(34, 291), (33, SAMPLE_ACTOR_ID)])
def test_sample_fight_data_only_for_the_reference(fight_id, actor_id):
    with pytest.raises(FightDataNotAvailableError):
        SampleReportSource().get_fight_data(SAMPLE_REPORT_CODE, fight_id, actor_id)


def test_sample_fight_data_of_other_report():
    with pytest.raises(ReportNotAvailableError):
        SampleReportSource().get_fight_data("OUTRO", 34, SAMPLE_ACTOR_ID)


def test_sample_prefetch_is_ready_without_cost():
    assert SampleReportSource().prefetch(SAMPLE_REPORT_CODE, 34, SAMPLE_ACTOR_ID) == "ready"
