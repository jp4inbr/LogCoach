"""Eventos da luta do jogador: cache, single-flight e pré-busca (nada aqui acessa a internet).

As buscas "lentas" esperam um `threading.Event` que o teste libera; nenhum teste depende de
sleep, e o `fresh_wcl_state` desliga o executor da pré-busca no fim de cada um. A fila é um
executor de 1 thread ocupado por uma tarefa presa (`busy_pool`): o que entra depois fica na
fila até o teste liberar.
"""

import gzip
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_sources import (  # noqa: F401 (fixture autouse)
    FakeWcl,
    LockProbe,
    fresh_wcl_state,
    wait_prefetch,
)

from app.services.sources import (
    PREFETCH_WORKERS,
    SAMPLE_ACTOR_ID,
    SAMPLE_REPORT_CODE,
    SAMPLES_DIR,
    SHUTDOWN_MESSAGE,
    FightDataNotAvailableError,
    FightDataStore,
    FightKey,
    PrefetchLimiter,
    PrefetchLimitError,
    ReportNotAvailableError,
    SampleReportSource,
    SourceUnavailableError,
    prefetch_executor,
    sample_fight_file,
    shutdown_prefetch,
)
from app.wcl.client import TIMEOUT_MESSAGE

FIXTURES_DIR = SAMPLES_DIR.parent.parent / "tests" / "fixtures"

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
    wait_prefetch()

    assert source.prefetch(*FIGHT) == "ready"
    assert wcl.count("FightMeta") == 1


def test_fight_data_after_prefetch_does_not_call_the_api():
    wcl = FakeWcl()
    source = wcl.source()
    source.prefetch(*FIGHT)
    wait_prefetch()  # espera a pré-busca terminar
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
        wait_prefetch()
    assert "Pré-busca" in caplog.text

    # A API voltou: a próxima chamada tenta de novo (nada de erro guardado).
    wcl.status = 200
    assert source.prefetch(*FIGHT) == "started"
    wait_prefetch()
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


def test_timeout_error_carries_the_report_code():
    # O erro de espera leva o código do report, não a chave (código, luta, ator).
    store = FightDataStore()
    key = FightKey(*FIGHT)
    gate, started = threading.Event(), threading.Event()

    def slow():
        started.set()
        assert gate.wait(timeout=5)
        return {"ok": True}, True

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(store.get, key, slow)
        assert started.wait(timeout=5)
        try:
            with pytest.raises(SourceUnavailableError) as info:
                store.get(key, lambda: pytest.fail("não pode baixar de novo"), wait_s=0.01)
        finally:
            gate.set()
        assert first.result(timeout=5) == {"ok": True}

    assert str(info.value) == "TESTE123"
    assert info.value.user_message == TIMEOUT_MESSAGE


def test_store_copies_outside_its_lock():
    # ~4,5 MB por luta: nem o lock do store nem o do cache ficam presos na cópia.
    store = FightDataStore()
    probe = LockProbe(store._lock, store._cache._lock)

    store.get("chave", lambda: (probe, True))
    store.get("chave", lambda: pytest.fail("estava no cache"))

    assert probe.locked_on_copy == [False, False]


# --- Fila da pré-busca --------------------------------------------------------------


@pytest.fixture
def busy_pool():
    """Executor de 1 thread ocupado: o que for submetido fica na fila até `gate.set()`."""
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="teste-fila")
    gate, busy = threading.Event(), threading.Event()

    def block():
        busy.set()
        assert gate.wait(timeout=5), "o teste não liberou a fila"

    pool.submit(block)
    assert busy.wait(timeout=5)
    yield pool, gate
    gate.set()
    pool.shutdown(wait=True)


def drain(pool, gate) -> None:
    gate.set()
    pool.shutdown(wait=True)


def test_engine_does_not_wait_for_a_queued_prefetch(busy_pool):
    # A pré-busca está na fila atrás de outra: o motor busca na hora, sem esperar a fila.
    pool, gate = busy_pool
    wcl = FakeWcl()
    source = wcl.source(executor=pool)
    assert source.prefetch(*FIGHT, client="ana") == "started"

    with ThreadPoolExecutor(max_workers=1) as caller:
        # Se esperasse a fila, ficaria preso até o gate: o timeout pega o erro.
        data = caller.submit(source.get_fight_data, *FIGHT).result(timeout=5)

    assert data["player"]["actor"]["id"] == 10
    assert wcl.count("FightMeta") == 1
    drain(pool, gate)
    # A tarefa da fila foi cancelada (ou não fez nada): nada de baixar de novo.
    assert wcl.count("FightMeta") == 1
    assert source.prefetch(*FIGHT, client="ana") == "ready"


def test_engine_waits_for_a_prefetch_that_already_started():
    # Já baixando (não só na fila): espera a mesma busca, sem baixar duas vezes.
    wcl = FakeWcl()
    wcl.gate = threading.Event()
    source = wcl.source()
    assert source.prefetch(*FIGHT, client="ana") == "started"
    assert wcl.fetching.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=1) as caller:
        waiting = caller.submit(source.get_fight_data, *FIGHT)
        wcl.gate.set()
        assert waiting.result(timeout=5)["player"]["actor"]["id"] == 10

    assert wcl.count("FightMeta") == 1


def test_new_prefetch_of_the_same_client_replaces_the_queued_one(busy_pool):
    pool, gate = busy_pool
    wcl = FakeWcl()
    source = wcl.source(executor=pool)

    assert source.prefetch("TESTE123", 2, 10, client="ana") == "started"
    assert source.prefetch("TESTE123", 2, 13, client="ana") == "started"
    # A do ator 10 saiu da fila: quem pede de novo começa outra, não "running".
    assert source.prefetch("TESTE123", 2, 10, client="bia") == "started"
    drain(pool, gate)

    assert source.prefetch("TESTE123", 2, 13) == "ready"
    assert source.prefetch("TESTE123", 2, 10) == "ready"
    assert wcl.count("FightMeta") == 2


def test_replaced_prefetch_stays_when_another_client_wants_it(busy_pool):
    pool, gate = busy_pool
    wcl = FakeWcl()
    source = wcl.source(executor=pool)

    assert source.prefetch("TESTE123", 2, 10, client="ana") == "started"
    assert source.prefetch("TESTE123", 2, 10, client="bia") == "running"
    assert source.prefetch("TESTE123", 2, 13, client="ana") == "started"
    assert source.prefetch("TESTE123", 2, 10, client="caio") == "running"  # continua na fila
    drain(pool, gate)

    assert source.prefetch("TESTE123", 2, 10) == "ready"
    assert source.prefetch("TESTE123", 2, 13) == "ready"
    assert wcl.count("FightMeta") == 2


def test_same_fight_again_keeps_its_place_in_the_queue(busy_pool):
    pool, gate = busy_pool
    wcl = FakeWcl()
    source = wcl.source(executor=pool)

    assert source.prefetch(*FIGHT, client="ana") == "started"
    assert source.prefetch(*FIGHT, client="ana") == "running"
    drain(pool, gate)

    assert source.prefetch(*FIGHT, client="ana") == "ready"
    assert wcl.count("FightMeta") == 1


def test_prefetch_limit_counts_only_new_fetches(busy_pool):
    pool, gate = busy_pool
    wcl = FakeWcl()
    source = wcl.source(executor=pool, limiter=PrefetchLimiter(max_calls=2))

    assert source.prefetch("TESTE123", 2, 10, client="ana") == "started"  # 1ª
    assert source.prefetch("TESTE123", 2, 10, client="ana") == "running"  # não conta
    assert source.prefetch("TESTE123", 2, 13, client="ana") == "started"  # 2ª
    with pytest.raises(PrefetchLimitError):
        source.prefetch("TESTE123", 2, 11, client="ana")
    # Negada sem mexer em nada: a do 13 continua na fila; outro cliente tem o próprio limite.
    assert source.prefetch("TESTE123", 2, 13, client="bia") == "running"
    assert source.prefetch("TESTE123", 2, 11, client="bia") == "started"
    drain(pool, gate)

    # Do cache não conta, mesmo com o limite estourado.
    assert source.prefetch("TESTE123", 2, 13, client="ana") == "ready"
    assert wcl.count("FightMeta") == 2


def test_limiter_window_slides():
    now = [0.0]
    limiter = PrefetchLimiter(max_calls=2, window_s=600, clock=lambda: now[0])

    assert [limiter.take("ana"), limiter.take("ana"), limiter.take("ana")] == [True, True, False]
    assert limiter.take("bia") is True
    now[0] = 599
    assert limiter.take("ana") is False
    now[0] = 600
    assert limiter.take("ana") is True
    assert all(limiter.take(None) for _ in range(5))  # sem cliente, sem limite


def test_limiter_defaults():
    # 10 pré-buscas novas a cada 10 min por cliente.
    now = [0.0]
    limiter = PrefetchLimiter(clock=lambda: now[0])

    assert all(limiter.take("ana") for _ in range(10))
    assert limiter.take("ana") is False
    now[0] = 10 * 60
    assert limiter.take("ana") is True


# --- Desligamento -------------------------------------------------------------------


def test_shutdown_cancels_the_queue_and_fails_its_fetches():
    # Os workers do processo estão ocupados; a pré-busca fica na fila. Desligar não roda a
    # fila: a busca falha com SHUTDOWN_MESSAGE (ninguém trava esperando) e nada é baixado.
    gate = threading.Event()
    busy = threading.Barrier(PREFETCH_WORKERS + 1)

    def block():
        busy.wait(timeout=5)
        assert gate.wait(timeout=5)

    executor = prefetch_executor()
    for _ in range(PREFETCH_WORKERS):
        executor.submit(block)
    busy.wait(timeout=5)
    wcl = FakeWcl()
    store = FightDataStore()
    source = wcl.source(fight_data=store)
    assert source.prefetch(*FIGHT, client="ana") == "started"
    flight = store._running[FightKey(*FIGHT)]

    stopping = threading.Thread(target=shutdown_prefetch)
    stopping.start()
    try:
        # Falha antes de os workers ocupados terminarem: não esperou a fila.
        error = flight.future.exception(timeout=5)
    finally:
        gate.set()
        stopping.join(timeout=5)

    assert not stopping.is_alive()
    assert isinstance(error, SourceUnavailableError)
    assert error.user_message == SHUTDOWN_MESSAGE
    assert str(error) == "TESTE123"
    assert wcl.count("FightMeta") == 0
    # Nada fica "running" para sempre: a próxima pré-busca começa de novo.
    assert source.prefetch(*FIGHT, client="ana") == "started"


# --- Modo exemplo -------------------------------------------------------------------


def reference_fixture() -> dict:
    """O kill de referência que o save_fixtures.py salvou em tests/fixtures/<bracket>/."""
    for index in sorted(FIXTURES_DIR.glob("*/index.json")):
        reference = json.loads(index.read_text(encoding="utf-8"))["reference"]
        if (reference["report"], reference["fight"]) == (SAMPLE_REPORT_CODE, 34):
            return json.loads(gzip.decompress((index.parent / reference["file"]).read_bytes()))
    pytest.fail("Kill de referência não está em tests/fixtures")


def test_sample_fight_is_inside_the_app():
    # O plano B vai junto com o app num deploy (o pacote é só `app*`), sem ler tests/.
    path = sample_fight_file(SAMPLE_REPORT_CODE, 34, SAMPLE_ACTOR_ID)

    assert path.parent == SAMPLES_DIR
    assert path.exists()


def test_sample_fight_is_the_same_as_the_reference_fixture():
    # Se o save_fixtures.py baixar de novo, as duas cópias não podem divergir.
    path = sample_fight_file(SAMPLE_REPORT_CODE, 34, SAMPLE_ACTOR_ID)

    assert json.loads(gzip.decompress(path.read_bytes())) == reference_fixture()


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
