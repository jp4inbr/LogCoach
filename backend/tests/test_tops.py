"""Fonte dos tops (`services/tops.py`): cache na memória e no banco, RF21, plano B, teto e
falhas lembradas. O WCL é falso (`fetch_tops`/`fetch_brackets` trocados); o banco é SQLite
em memória."""

import gzip
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from app import models  # noqa: F401  (tabelas)
from app.services import tops as tops_module
from app.services.sources import (
    ClientLimiter,
    FightDataStore,
    PrefetchLimitError,
    ReportCache,
    SourceUnavailableError,
    WclCooldown,
)
from app.services.tops import (
    BRACKETS_TTL_S,
    SAMPLE_TOPS_DIR,
    TOPS_FAILURE_TTL_S,
    TOPS_LIMIT_MESSAGE,
    TOPS_TTL_S,
    OwnLog,
    SampleTopsSource,
    TopsDb,
    TopsNotAvailableError,
    WclTopsSource,
)
from app.wcl.client import WclError, WclUnavailableError

FIXTURES = Path(__file__).parent / "fixtures" / "nekzali_mythic_326_328"
OWN = OwnLog("MEU", 1, "Eu")
BRACKETS = {"min": 272, "max": 400, "bucket": 3, "type": "itemLevel"}  # 327 → 19 (326–328)


def raw_tops(n: int = 11, own_at: int | None = None, skip: tuple[int, ...] = ()) -> dict:
    """Saída de `fetch_tops`: posições 1..n; `own_at` põe o log analisado nessa posição;
    `skip` são posições cuja luta não abriu."""
    ids = [
        {"rank": i, "report": f"B{i}", "fight_id": i, "name": f"Mago{i}", "server": "Area 52"}
        for i in range(1, n + 1)
    ]
    if own_at is not None:
        ids[own_at - 1].update(report=OWN.report, fight_id=OWN.fight_id, name=OWN.name)
    return {
        "rankings": ids,
        "tops": [
            {
                "rank": r["rank"],
                "ranking": {
                    "name": r["name"],
                    "server": {"name": r["server"]},
                    "amount": 300_000 - r["rank"],
                    "duration": 400_000,
                    "bracketData": 327,
                    "report": {"code": r["report"], "fightID": r["fight_id"]},
                },
                "fight": {"meta": {"report": r["report"]}, "n": r["rank"]},
            }
            for r in ids
            if r["rank"] not in skip
        ],
        "skipped": [],
    }


class FakeWcl:
    def __init__(self) -> None:
        self.tops_calls: list = []
        self.bracket_calls = 0
        self.error: Exception | None = None
        self.raw = raw_tops()
        self.gate: threading.Event | None = None  # segura a busca (single-flight)

    def fetch_tops(self, client, encounter_id, class_name, spec_name, difficulty, bracket, n):
        self.tops_calls.append((bracket, n))
        if self.gate is not None:
            self.gate.wait(5)
        if self.error is not None:
            raise self.error
        return self.raw

    def fetch_brackets(self, client, encounter_id):
        self.bracket_calls += 1
        if self.error is not None:
            raise self.error
        return BRACKETS


@pytest.fixture
def wcl(monkeypatch):
    fake = FakeWcl()
    monkeypatch.setattr(tops_module, "fetch_tops", fake.fetch_tops)
    monkeypatch.setattr(tops_module, "fetch_brackets", fake.fetch_brackets)
    return fake


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return TopsDb(engine)


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def make_source(db, clock=None, executor=None, limit=2, sample=None, cooldown=None):
    """Fonte com estado próprio (memória, brackets, teto, pausa, falhas): um processo novo."""
    return WclTopsSource(
        client_factory=lambda: None,
        store=FightDataStore(ReportCache(ttl_s=3600, max_items=16)),
        brackets=ReportCache(ttl_s=3600),
        db=db,
        executor_factory=(lambda: executor) if executor else (lambda: None),
        limiter=ClientLimiter(global_max_calls=limit, global_window_s=3600),
        cooldown=WclCooldown() if cooldown is None else cooldown,
        failures=ReportCache(ttl_s=TOPS_FAILURE_TTL_S),
        sample=sample or SampleTopsSource(Path("/nao/existe")),
        clock=clock or Clock(),
    )


def test_bracket_top_10_with_names_and_fights(wcl, db):
    result = make_source(db).get_tops(3470, 5, 327.6, OWN)
    assert result.label == "Top 10 do bracket 326–328"
    assert result.bracket == "326–328"
    assert not result.player_in_top and not result.stale and not result.sample
    # 11 guardados, 10 na comparação.
    assert [e.display_name for e in result.entries] == [f"top{i:02d}" for i in range(1, 11)]
    first = result.entries[0]
    assert (first.name, first.server, first.item_level, first.report) == (
        "Mago1",
        "Area 52",
        327,
        "B1",
    )
    assert first.fight() == {"meta": {"report": "B1"}, "n": 1}
    assert first.compared().dps == 299_999
    assert wcl.tops_calls == [(19, 11)]


def test_rank_is_the_ranking_position_when_a_fight_did_not_open(wcl, db):
    wcl.raw = raw_tops(n=12, skip=(3,))
    entries = make_source(db).get_tops(3470, 5, 327, OWN).entries
    assert [e.rank for e in entries] == [1, 2, 4, 5, 6, 7, 8, 9, 10, 11]
    assert entries[2].display_name == "top04"


def test_rf21_analyzed_log_in_top_10_leaves_and_the_11th_comes_in(wcl, db):
    wcl.raw = raw_tops(own_at=4)
    result = make_source(db).get_tops(3470, 5, 327, OWN)
    assert result.player_in_top
    assert result.label == "Top 10 do bracket 326–328"  # mesma comparação, sem o top 10 geral
    assert [e.rank for e in result.entries] == [1, 2, 3, 5, 6, 7, 8, 9, 10, 11]
    assert wcl.tops_calls == [(19, 11)]  # nenhuma busca a mais


def test_rf21_counts_the_log_even_if_its_fight_did_not_open(wcl, db):
    wcl.raw = raw_tops(own_at=2, skip=(2,))
    result = make_source(db).get_tops(3470, 5, 327, OWN)
    assert result.player_in_top
    assert len(result.entries) == 10


def test_rf21_another_log_of_the_same_character_is_a_regular_top(wcl, db):
    # O top 4 é do mesmo personagem, mas de outro dia: entra na comparação.
    wcl.raw = raw_tops(own_at=4)
    other_day = OwnLog("OUTRO", 9, OWN.name)
    result = make_source(db).get_tops(3470, 5, 327, other_day)
    assert not result.player_in_top
    assert [e.rank for e in result.entries] == list(range(1, 11))
    assert result.entries[3].name == OWN.name


def test_rf21_raid_mate_in_the_same_fight_is_not_the_player(wcl, db):
    wcl.raw = raw_tops(own_at=4)
    mate = OwnLog(OWN.report, OWN.fight_id, "Colega")
    result = make_source(db).get_tops(3470, 5, 327, mate)
    assert not result.player_in_top
    assert [e.rank for e in result.entries] == list(range(1, 11))


def test_rf21_name_comparison_ignores_case(wcl, db):
    wcl.raw = raw_tops(own_at=1)
    assert make_source(db).get_tops(3470, 5, 327, OwnLog("MEU", 1, "EU")).player_in_top


def test_item_level_outside_the_brackets_has_no_tops(wcl, db):
    for item_level in (200, 500):
        with pytest.raises(TopsNotAvailableError):
            make_source(db).get_tops(3470, 5, item_level, OWN)
    assert wcl.tops_calls == []


def test_memory_then_database_then_expiry(wcl, db):
    clock = Clock()
    source = make_source(db, clock)
    source.get_tops(3470, 5, 327, OWN)
    source.get_tops(3470, 5, 328, OWN)  # mesmo bracket, da memória
    assert len(wcl.tops_calls) == 1 and wcl.bracket_calls == 1

    # "Reinício": memória vazia, o banco ainda vale (tops e brackets): nada vai ao WCL.
    restarted = make_source(db, clock)
    entries = restarted.get_tops(3470, 5, 327, OWN).entries
    assert len(wcl.tops_calls) == 1 and wcl.bracket_calls == 1
    assert entries[3].fight() == {"meta": {"report": "B4"}, "n": 4}

    clock.now += max(TOPS_TTL_S, BRACKETS_TTL_S) + 1
    make_source(db, clock).get_tops(3470, 5, 327, OWN)
    assert len(wcl.tops_calls) == 2 and wcl.bracket_calls == 2


def test_single_flight_two_threads_one_fetch(wcl, db):
    wcl.gate = threading.Event()
    source = make_source(db)
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(source.get_tops(3470, 5, 327, OWN)))
        for _ in range(2)
    ]
    for t in threads:
        t.start()
    time.sleep(0.1)
    wcl.gate.set()
    for t in threads:
        t.join(5)
    assert len(results) == 2 and len(wcl.tops_calls) == 1


def test_wcl_down_after_restart_uses_expired_database_copies(wcl, db):
    clock = Clock()
    make_source(db, clock).get_tops(3470, 5, 327, OWN)
    clock.now += max(TOPS_TTL_S, BRACKETS_TTL_S) + 1
    wcl.error = WclUnavailableError("fora do ar", status=503)
    # Processo novo: nem os brackets estão na memória; os do banco, vencidos, servem.
    source = make_source(db, clock)
    result = source.get_tops(3470, 5, 327, OWN)
    assert result.stale and len(result.entries) == 10
    # Vencido não vai para a memória: com o WCL de volta (e a pausa e a falha esquecidas),
    # busca de novo.
    wcl.error = None
    source._cooldown.clear()
    source._failures.clear()
    assert not source.get_tops(3470, 5, 327, OWN).stale


def test_wcl_down_without_copy_uses_sample_bracket_or_fails(wcl, db):
    wcl.error = WclUnavailableError("fora do ar", status=503)
    with pytest.raises(SourceUnavailableError):
        make_source(db).get_tops(3470, 5, 327, OWN)

    sample = make_source(db, sample=SampleTopsSource()).get_tops(3470, 5, 327, OWN)
    assert sample.sample and len(sample.entries) == 10

    # Fora do bracket do exemplo, vale o erro do WCL.
    with pytest.raises(SourceUnavailableError):
        make_source(db, sample=SampleTopsSource()).get_tops(3470, 5, 340, OWN)


def test_wcl_down_turns_on_the_process_pause(wcl, db):
    cooldown = WclCooldown()
    wcl.error = WclUnavailableError("limite", rate_limited=True)
    with pytest.raises(SourceUnavailableError):
        make_source(db, cooldown=cooldown).get_tops(3470, 5, 327, OWN)
    assert cooldown.active() is not None
    calls = wcl.bracket_calls
    with pytest.raises(SourceUnavailableError):
        make_source(db, cooldown=cooldown).get_tops(3470, 5, 327, OWN)
    assert wcl.bracket_calls == calls  # nem chamou a API


def test_failed_bracket_fetch_is_remembered_for_a_while(wcl, db):
    source = make_source(db)
    source._brackets.put(3470, BRACKETS)
    # Timeout não liga a pausa do processo, mas a busca desse bracket não se repete.
    wcl.error = WclUnavailableError("demorou", status=None)
    with pytest.raises(SourceUnavailableError):
        source.get_tops(3470, 5, 327, OWN)
    assert source._cooldown.active() is None
    wcl.error = None
    with pytest.raises(SourceUnavailableError):
        source.get_tops(3470, 5, 327, OWN)
    assert len(wcl.tops_calls) == 1
    source._failures.clear()  # passaram os 5 min
    assert source.get_tops(3470, 5, 327, OWN).entries
    assert len(wcl.tops_calls) == 2


def test_empty_ranking_or_refused_query_has_no_tops(wcl, db):
    wcl.raw = {"rankings": [], "tops": [], "skipped": []}
    with pytest.raises(TopsNotAvailableError):
        make_source(db).get_tops(3470, 5, 327, OWN)
    wcl.error = WclError("encontro sem ranking")
    with pytest.raises(TopsNotAvailableError):
        make_source(db).get_tops(3470, 5, 327, OWN)


def test_fill_limit_is_shared_by_prefetch_and_analysis(wcl, db):
    source = make_source(db, limit=1)
    source.get_tops(3470, 5, 327, OWN, prefetch=True)  # bracket 19: usa a vaga
    with pytest.raises(PrefetchLimitError):
        source.get_tops(3470, 5, 335, OWN, prefetch=True)  # bracket novo na pré-busca: para
    with pytest.raises(SourceUnavailableError) as exc:
        source.get_tops(3470, 5, 335, OWN)  # na análise: erro com a mensagem do teto
    assert exc.value.user_message == TOPS_LIMIT_MESSAGE
    assert len(wcl.tops_calls) == 1
    assert source.get_tops(3470, 5, 327, OWN).entries  # bracket já guardado: sem teto


def test_analysis_waiting_a_prefetch_that_hit_the_limit_tries_itself(wcl, db):
    source = make_source(db, limit=2)
    original = source._fill
    calls = []

    def fill(key, prefetch):
        calls.append(prefetch)
        if prefetch:
            raise PrefetchLimitError(key.code)
        return original(key, prefetch)

    source._fill = fill
    key = tops_module.TopsKey(3470, 5, 19)
    with pytest.raises(PrefetchLimitError):
        source._snapshot(key, prefetch=True)
    calls.clear()

    # A análise chega enquanto a pré-busca está baixando e recebe o erro dela: tenta sozinha.
    gate, started = threading.Event(), threading.Event()

    def slow_fill(key, prefetch):
        calls.append(prefetch)
        if prefetch:
            started.set()
            gate.wait(5)
            raise PrefetchLimitError(key.code)
        return original(key, prefetch)

    source._fill = slow_fill

    def run_prefetch():
        with pytest.raises(PrefetchLimitError):
            source._snapshot(key, True)

    prefetch = threading.Thread(target=run_prefetch)
    prefetch.start()
    assert started.wait(5)
    result = []
    analysis = threading.Thread(target=lambda: result.append(source._snapshot(key, False)))
    analysis.start()
    time.sleep(0.1)
    gate.set()
    prefetch.join(5)
    analysis.join(5)
    assert result and result[0].entries
    assert calls == [True, False]


def test_database_failure_only_logs(wcl, caplog):
    broken = create_engine("sqlite://", poolclass=StaticPool)  # sem as tabelas
    result = make_source(TopsDb(broken)).get_tops(3470, 5, 327, OWN)
    assert len(result.entries) == 10
    assert "falha ao gravar no banco" in caplog.text


def test_prefetch_runs_in_background_and_dedupes(wcl, db):
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        source = make_source(db, executor=executor)
        wcl.gate = threading.Event()
        source.prefetch_tops(3470, 5, 327, OWN)
        source.prefetch_tops(3470, 5, 327, OWN)  # o mesmo pedido já está na fila
        wcl.gate.set()
    finally:
        executor.shutdown(wait=True)
    assert len(wcl.tops_calls) == 1
    assert source.get_tops(3470, 5, 327, OWN).entries  # já no cache
    assert len(wcl.tops_calls) == 1


def test_prefetch_failure_only_logs(wcl, db, caplog):
    wcl.error = WclUnavailableError("fora do ar", status=503)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        make_source(db, executor=executor).prefetch_tops(3470, 5, 327, OWN)
    finally:
        executor.shutdown(wait=True)
    assert "Pré-busca dos tops" in caplog.text


# --- Exemplo ---------------------------------------------------------------------


def test_sample_tops_are_the_fixture_tops_byte_for_byte():
    sample_dir = SAMPLE_TOPS_DIR / FIXTURES.name
    files = sorted(p.name for p in sample_dir.iterdir())
    assert files == ["index.json"] + [f"top{i:02d}.json.gz" for i in range(1, 11)]
    for name in files:
        assert (sample_dir / name).read_bytes() == (FIXTURES / name).read_bytes(), name


def test_sample_source_reads_the_reference_bracket():
    harmonist = OwnLog("XhrmBaYkGCAQjH2D", 34, "Harmonist")
    result = SampleTopsSource().get_tops(3470, 5, 327, harmonist)
    assert result.sample and not result.player_in_top
    assert result.label == "Top 10 do bracket 326–328"
    assert [e.rank for e in result.entries] == list(range(1, 11))
    assert all(e.name is None and e.report is None for e in result.entries)
    fight = result.entries[0].fight()
    assert fight["player"]["actor"]["display_name"] == "top01"
    with pytest.raises(TopsNotAvailableError):
        SampleTopsSource().get_tops(3470, 5, 340, harmonist)
    with pytest.raises(TopsNotAvailableError):
        SampleTopsSource().get_tops(3470, 4, 327, harmonist)


def test_sample_copies_have_only_pseudonyms():
    """Vale no CI (sem o names.local.json): atores Player só com pseudônimo, sem nome, reino
    nem o código do report."""
    sample_dir = SAMPLE_TOPS_DIR / FIXTURES.name
    for path in sorted(sample_dir.glob("top*.json.gz")):
        fight = json.loads(gzip.decompress(path.read_bytes()))
        players = [a for a in fight["actors"] if a["type"] == "Player"]
        assert players and all("name" not in a and "server" not in a for a in players), path
        assert all(a["display_name"].startswith(("top", "raid_")) for a in players), path
        assert fight["meta"]["report"] is None, path


def test_sample_copies_have_no_real_names():
    names_file = FIXTURES.parent / "names.local.json"
    if not names_file.exists():
        pytest.skip("names.local.json só existe na máquina de quem baixou as fixtures")
    real = json.loads(names_file.read_text(encoding="utf-8")).get(FIXTURES.name, {})
    # Só jogadores: os pets têm nome de magia ("Mirror Image"), que aparece nas habilidades.
    names = {
        v["name"]
        for fixture in real.values()
        for label, v in fixture.items()
        if not label.startswith("pet_") and isinstance(v, dict) and v.get("name")
    }
    assert names
    sample_dir = SAMPLE_TOPS_DIR / FIXTURES.name
    for path in sample_dir.iterdir():
        raw = path.read_bytes()
        text = (gzip.decompress(raw) if path.suffix == ".gz" else raw).decode("utf-8")
        assert not any(name in text for name in names), path.name
