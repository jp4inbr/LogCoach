"""Fonte dos tops (`services/tops.py`): cache na memória e no banco, RF21, plano B e teto da
pré-busca. O WCL é falso (`fetch_tops`/`fetch_brackets` trocados); o banco é SQLite em
memória."""

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
    SAMPLE_TOPS_DIR,
    TOPS_TTL_S,
    SampleTopsSource,
    TopsDb,
    TopsNotAvailableError,
    WclTopsSource,
)
from app.wcl.client import WclError, WclUnavailableError

FIXTURES = Path(__file__).parent / "fixtures" / "nekzali_mythic_326_328"
OWN = ("MEU", 1)
BRACKETS = {"min": 272, "max": 400, "bucket": 3, "type": "itemLevel"}  # 327 → 19 (326–328)


def raw_tops(prefix: str, n: int = 10, own_at: int | None = None) -> dict:
    """Saída de `fetch_tops` com n tops; `own_at` põe o log do jogador nessa posição."""
    logs = [(f"{prefix}{i}", i) for i in range(1, n + 1)]
    if own_at is not None:
        logs[own_at - 1] = OWN
    return {
        "ranking_logs": logs,
        "tops": [
            {
                "ranking": {
                    "name": f"Mago{prefix}{i}",
                    "server": {"name": "Area 52"},
                    "amount": 300_000 - i,
                    "duration": 400_000,
                    "bracketData": 327,
                    "report": {"code": code, "fightID": fight},
                },
                "fight": {"meta": {"report": code}, "n": i},
            }
            for i, (code, fight) in enumerate(logs, start=1)
        ],
        "skipped": [],
    }


class FakeWcl:
    def __init__(self) -> None:
        self.tops_calls: list = []
        self.bracket_calls = 0
        self.error: Exception | None = None
        self.own_at: int | None = None  # posição do log do jogador no bracket
        self.general_own_at: int | None = None
        self.gate: threading.Event | None = None  # segura a busca (single-flight)

    def fetch_tops(self, client, encounter_id, class_name, spec_name, difficulty, bracket):
        self.tops_calls.append(bracket)
        if self.gate is not None:
            self.gate.wait(5)
        if self.error is not None:
            raise self.error
        if bracket is None:
            return raw_tops("G", own_at=self.general_own_at)
        return raw_tops("B", own_at=self.own_at)

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
    """Fonte com estado próprio (memória, brackets, teto, pausa): como um processo novo."""
    return WclTopsSource(
        client_factory=lambda: None,
        store=FightDataStore(ReportCache(ttl_s=3600, max_items=16)),
        brackets=ReportCache(ttl_s=3600),
        db=db,
        executor_factory=(lambda: executor) if executor else (lambda: None),
        limiter=ClientLimiter(global_max_calls=limit, global_window_s=3600),
        cooldown=WclCooldown() if cooldown is None else cooldown,
        sample=sample or SampleTopsSource(Path("/nao/existe")),
        clock=clock or Clock(),
    )


def test_bracket_tops_come_with_names_and_fights(wcl, db):
    result = make_source(db).get_tops(3470, 5, 327.6, OWN)
    assert result.label == "Top 10 do bracket 326–328"
    assert result.bracket == "326–328"
    assert not result.player_in_top and not result.stale and not result.sample
    assert [e.display_name for e in result.entries] == [f"top{i:02d}" for i in range(1, 11)]
    first = result.entries[0]
    assert (first.name, first.server, first.item_level, first.report) == (
        "MagoB1", "Area 52", 327, "B1"
    )  # fmt: skip
    assert first.fight() == {"meta": {"report": "B1"}, "n": 1}
    assert first.compared().dps == 299_999
    assert wcl.tops_calls == [19]


def test_memory_then_database_then_expiry(wcl, db):
    clock = Clock()
    source = make_source(db, clock)
    source.get_tops(3470, 5, 327, OWN)
    source.get_tops(3470, 5, 328, OWN)  # mesmo bracket, da memória
    assert wcl.tops_calls == [19] and wcl.bracket_calls == 1

    # "Reinício": memória vazia, o banco ainda vale. Só os brackets (1 ponto) vão ao WCL.
    restarted = make_source(db, clock)
    entries = restarted.get_tops(3470, 5, 327, OWN).entries
    assert wcl.tops_calls == [19]
    assert entries[3].fight() == {"meta": {"report": "B4"}, "n": 4}

    clock.now += TOPS_TTL_S + 1
    make_source(db, clock).get_tops(3470, 5, 327, OWN)
    assert wcl.tops_calls == [19, 19]


def test_rf21_player_in_bracket_top_compares_with_general_without_own_log(wcl, db):
    wcl.own_at = 4
    wcl.general_own_at = 9
    result = make_source(db).get_tops(3470, 5, 327, OWN)
    assert result.player_in_top
    assert result.label == "Top 10 geral" and result.bracket == "326–328"
    assert len(result.entries) == 9
    assert all((e.report, e.fight_id) != OWN for e in result.entries)
    assert wcl.tops_calls == [19, None]


def test_rf21_counts_own_log_even_if_its_fight_did_not_open(wcl, db, monkeypatch):
    def fetch(client, encounter_id, class_name, spec_name, difficulty, bracket):
        if bracket is None:
            return raw_tops("G")
        raw = raw_tops("B", own_at=2)
        raw["tops"] = [t for t in raw["tops"] if t["ranking"]["report"]["code"] != "MEU"]
        return raw

    monkeypatch.setattr(tops_module, "fetch_tops", fetch)
    assert make_source(db).get_tops(3470, 5, 327, OWN).player_in_top


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
    assert len(results) == 2 and wcl.tops_calls == [19]


def test_wcl_down_serves_expired_database_copy_as_stale(wcl, db):
    clock = Clock()
    make_source(db, clock).get_tops(3470, 5, 327, OWN)
    clock.now += TOPS_TTL_S + 1
    wcl.error = WclUnavailableError("fora do ar", status=503)
    source = make_source(db, clock)
    # Os brackets já estão na memória do processo; só os tops falham.
    source._brackets.put(3470, BRACKETS)
    result = source.get_tops(3470, 5, 327, OWN)
    assert result.stale and len(result.entries) == 10
    # Vencido não vai para a memória: com o WCL de volta, busca de novo.
    wcl.error = None
    source._cooldown.clear()
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


def test_empty_ranking_or_refused_query_has_no_tops(wcl, db, monkeypatch):
    monkeypatch.setattr(
        tops_module, "fetch_tops", lambda *a: {"ranking_logs": [], "tops": [], "skipped": []}
    )
    with pytest.raises(TopsNotAvailableError):
        make_source(db).get_tops(3470, 5, 327, OWN)
    wcl.error = WclError("encontro sem ranking")
    with pytest.raises(TopsNotAvailableError):
        make_source(db).get_tops(3470, 5, 327, OWN)


def test_prefetch_fill_limit_only_applies_to_prefetch(wcl, db):
    source = make_source(db, limit=1)
    source.get_tops(3470, 5, 327, OWN, prefetch=True)  # bracket 19: usa a vaga
    with pytest.raises(PrefetchLimitError):
        source.get_tops(3470, 5, 335, OWN, prefetch=True)  # bracket novo: teto
    assert len(source.get_tops(3470, 5, 335, OWN).entries) == 10  # a análise busca
    assert wcl.tops_calls == [19, 22]


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
    assert wcl.tops_calls == [19]
    assert source.get_tops(3470, 5, 327, OWN).entries  # já no cache
    assert wcl.tops_calls == [19]


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
    result = SampleTopsSource().get_tops(3470, 5, 327, ("XhrmBaYkGCAQjH2D", 34))
    assert result.sample and not result.player_in_top
    assert result.label == "Top 10 do bracket 326–328"
    assert [e.rank for e in result.entries] == list(range(1, 11))
    assert all(e.name is None and e.report is None for e in result.entries)
    fight = result.entries[0].fight()
    assert fight["player"]["actor"]["display_name"] == "top01"
    with pytest.raises(TopsNotAvailableError):
        SampleTopsSource().get_tops(3470, 5, 340, ("XhrmBaYkGCAQjH2D", 34))
    with pytest.raises(TopsNotAvailableError):
        SampleTopsSource().get_tops(3470, 4, 327, ("XhrmBaYkGCAQjH2D", 34))


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
        assert not any(f'"{name}"' in text for name in names), path.name
