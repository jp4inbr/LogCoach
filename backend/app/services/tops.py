"""Os top 10 com quem o jogador é comparado (RF21, RNF03, item 12.13).

`get_tops_source()` escolhe pela DATA_SOURCE, como `get_report_source()`:
- "wcl": `WclTopsSource` busca no Warcraft Logs os 10 melhores do mesmo encontro,
  dificuldade e bracket de item level, com a luta completa de cada um (~180 pontos). Guarda
  por 24 h no banco (um reinício do processo não gasta os pontos de novo) e, na frente, na
  memória (1 h, single-flight: quem pede um bracket que está baixando espera essa busca).
  Se o jogador já está no top 10 do bracket (RF21), compara com o top 10 geral, sem o
  próprio log. A pré-busca (`prefetch_tops`) pede os tops em segundo plano quando o jogador
  fica definido, com teto de brackets novos por hora no processo.
- "exemplo": `SampleTopsSource` lê a cópia dos tops do kill de referência em
  `app/samples/tops/` (plano B da demo e do WCL fora do ar).

As lutas ficam comprimidas (`TopEntry.fight_gz`, ~130 KB); `TopEntry.fight()` descomprime
uma de cada vez (~4,5 MB na memória cada).
"""

import gzip
import json
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, NamedTuple, Protocol

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, delete, select

from app.config import get_settings
from app.models import TopsLog, TopsSnapshot
from app.schemas import ComparedPlayer
from app.services.sources import (
    ARCANE,
    SAMPLES_DIR,
    AnalysisNotAvailableError,
    ClientLimiter,
    FightDataStore,
    PrefetchLimitError,
    ReportCache,
    SourceUnavailableError,
    WclCooldown,
    _heavy_fetch_pauses,
    wcl_cooldown,
)
from app.wcl.client import (
    UNAVAILABLE_MESSAGE,
    WCL_UNAVAILABLE_CODE,
    WclClient,
    WclError,
    WclUnavailableError,
    shared_client,
)
from app.wcl.fetch import bracket_index, bracket_range, fetch_brackets
from app.wcl.tops import fetch_tops

logger = logging.getLogger(__name__)

TOP_N = 10
# RNF03: o top 10 de um bracket vale 24 h (no banco).
TOPS_TTL_S = 24 * 60 * 60
# Na memória, só 1 h: depois relê o banco, para um snapshot lido perto de vencer não ficar
# mais 24 h na memória. Até 16 snapshots (~1,3 MB cada, comprimidos).
TOPS_MEMORY_TTL_S = 60 * 60
TOPS_MEMORY_MAX = 16
# Brackets do encontro (mínimo e tamanho da faixa): mudam só de temporada.
BRACKETS_TTL_S = 24 * 60 * 60
# Quem precisa dos tops espera a busca em andamento (10 lutas levam de 1 a 3 min).
TOPS_WAIT_S = 300
# Teto da pré-busca: brackets novos buscados no WCL por hora no processo (~190 pontos cada).
# Com as 30 pré-buscas de luta por hora (~18 cada), fica em ~920 dos 1000 pontos/hora.
TOPS_FILL_LIMIT = 2
TOPS_FILL_WINDOW_S = 60 * 60

SAMPLE_TOPS_DIR = SAMPLES_DIR / "tops"


class TopsNotAvailableError(AnalysisNotAvailableError):
    """Sem tops para comparar: ranking vazio, encontro sem ranking ou fora do exemplo."""


class TopsKey(NamedTuple):
    """Chave de um top 10: bracket `None` é o ranking geral (RF21)."""

    encounter_id: int
    difficulty: int
    bracket: int | None

    @property
    def code(self) -> str:
        # Texto da chave: no banco e nas mensagens de erro (`_report_code` do store lê daqui).
        return f"{self.encounter_id}:{self.difficulty}:{self.bracket or 'geral'}"


@dataclass(frozen=True)
class TopEntry:
    """Um top: o que a tela mostra (`compared()`) e a luta comprimida."""

    rank: int  # posição no ranking
    display_name: str  # "top01"… (RF25), pela ordem das lutas obtidas
    name: str | None  # nome real (só para o botão de mostrar nomes; nunca para a IA)
    server: str | None
    item_level: int | None
    dps: float
    duration_ms: int | None
    report: str | None  # nulo nas cópias anonimizadas do exemplo
    fight_id: int | None
    fight_gz: bytes

    def fight(self) -> dict[str, Any]:
        """A luta no formato de `wcl.fetch.fetch_fight` (o motor lê com `measure`)."""
        return json.loads(gzip.decompress(self.fight_gz))

    def compared(self) -> ComparedPlayer:
        return ComparedPlayer(
            rank=self.rank,
            display_name=self.display_name,
            name=self.name,
            server=self.server,
            item_level=self.item_level,
            dps=self.dps,
        )

    def meta(self) -> dict[str, Any]:
        """Tudo menos a luta: o que vai para `TopsLog.meta`."""
        return {k: getattr(self, k) for k in META_FIELDS}


META_FIELDS = tuple(f for f in TopEntry.__dataclass_fields__ if f != "fight_gz")


@dataclass(frozen=True)
class TopsSet:
    """Um top 10 como veio do ranking (o que fica no banco e na memória)."""

    key: TopsKey
    fetched_at: float  # time.time() da busca no WCL
    # (report, luta) dos 10 primeiros do ranking, mesmo os que não abriram: é por eles que
    # se sabe se o jogador está no top 10 (RF21).
    ranking_logs: tuple[tuple[str, int], ...]
    entries: tuple[TopEntry, ...]
    stale: bool = False  # vencido, servido porque o WCL está fora do ar


@dataclass(frozen=True)
class TopsComparison:
    """Com quem comparar o jogador: o que o `EngineAnalyzer` (passo 4.3) vai ler."""

    label: str  # "Top 10 do bracket 326–328" ou "Top 10 geral"
    bracket: str  # faixa do jogador: "326–328"
    player_in_top: bool  # RF21: o jogador está no top 10 do bracket
    entries: tuple[TopEntry, ...]  # em ordem de rank, sem o próprio log do jogador
    stale: bool = False  # tops de mais de 24 h (WCL fora do ar)
    sample: bool = False  # cópia do exemplo (plano B)


Own = tuple[str, int]  # (código do report, id da luta) do jogador analisado


class TopsSource(Protocol):
    def get_tops(
        self, encounter_id: int, difficulty: int, item_level: float, own: Own
    ) -> TopsComparison:
        """Os tops do bracket do jogador (ou o top 10 geral, RF21). Pode esperar a busca."""
        ...

    def prefetch_tops(
        self, encounter_id: int, difficulty: int, item_level: float, own: Own
    ) -> None:
        """Pede os tops em segundo plano e volta na hora; falhas só no log."""
        ...


def compress_fight(fight: dict[str, Any]) -> bytes:
    raw = json.dumps(fight, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw, mtime=0)


def _bracket_text(low: int, high: int) -> str:
    return f"{low}–{high}"


def _comparison(
    bracket: TopsSet, low: int, high: int, own: Own, general: Callable[[], TopsSet]
) -> TopsComparison:
    """RF21: com o próprio log no top 10 do bracket, compara com o top 10 geral sem ele."""
    text = _bracket_text(low, high)
    if tuple(own) not in bracket.ranking_logs:
        return TopsComparison(
            label=f"Top {TOP_N} do bracket {text}",
            bracket=text,
            player_in_top=False,
            entries=bracket.entries,
            stale=bracket.stale,
        )
    overall = general()
    entries = tuple(e for e in overall.entries if (e.report, e.fight_id) != tuple(own))
    return TopsComparison(
        label=f"Top {TOP_N} geral",
        bracket=text,
        player_in_top=True,
        entries=entries,
        stale=overall.stale,
    )


# --- Exemplo -------------------------------------------------------------------


class SampleTopsSource:
    """Os tops do bracket do kill de referência (cópia das fixtures em `app/samples/tops/`).

    Só esse encontro, dificuldade e faixa de item level; o resto não tem tops no exemplo.
    """

    def __init__(self, directory: Path = SAMPLE_TOPS_DIR) -> None:
        self._dir = directory

    def get_tops(
        self, encounter_id: int, difficulty: int, item_level: float, own: Own
    ) -> TopsComparison:
        for index_file in sorted(self._dir.glob("*/index.json")):
            index = json.loads(index_file.read_text(encoding="utf-8"))
            bracket = index["bracket"]
            low, high = bracket["min_item_level"], bracket["max_item_level"]
            if (
                index["encounter_id"] == encounter_id
                and index["difficulty"] == difficulty
                and low <= int(item_level) <= high
            ):
                return self._load(index_file.parent, index, low, high)
        raise TopsNotAvailableError(
            f"Sem tops de exemplo para o encontro {encounter_id}, dificuldade {difficulty}, "
            f"item level {item_level}."
        )

    def prefetch_tops(
        self, encounter_id: int, difficulty: int, item_level: float, own: Own
    ) -> None:
        return None  # arquivos locais: nada a buscar

    @staticmethod
    def _load(directory: Path, index: dict[str, Any], low: int, high: int) -> TopsComparison:
        entries = tuple(
            TopEntry(
                rank=top["rank"],
                display_name=top["display_name"],
                name=None,  # anonimizado; o nome real vem do names.local.json, se houver
                server=None,
                item_level=top.get("bracket_item_level"),
                dps=top["amount"],
                duration_ms=top.get("duration_ms"),
                report=None,
                fight_id=None,
                fight_gz=(directory / top["file"]).read_bytes(),
            )
            for top in index["top"]
        )
        text = _bracket_text(low, high)
        return TopsComparison(
            label=f"Top {TOP_N} do bracket {text}",
            bracket=text,
            # O exemplo é o Harmonist, fora do top 10 (as cópias não guardam os reports).
            player_in_top=bool(index.get("reference_in_top")),
            entries=entries,
            sample=True,
        )


# --- Warcraft Logs ---------------------------------------------------------------


def _set_from_db(snapshot: TopsSnapshot, logs: list[TopsLog], key: TopsKey) -> TopsSet:
    entries = tuple(
        TopEntry(**{k: log.meta.get(k) for k in META_FIELDS}, fight_gz=log.fight_gz)
        for log in sorted(logs, key=lambda log: log.rank)
    )
    return TopsSet(
        key=key,
        fetched_at=snapshot.fetched_at,
        ranking_logs=tuple((code, fight) for code, fight in snapshot.info["ranking_logs"]),
        entries=entries,
    )


def _set_from_wcl(key: TopsKey, raw: dict[str, Any], fetched_at: float) -> TopsSet:
    entries = []
    for i, top in enumerate(raw["tops"], start=1):
        ranking = top["ranking"]
        entries.append(
            TopEntry(
                rank=i,
                display_name=f"top{i:02d}",
                name=ranking.get("name"),
                server=(ranking.get("server") or {}).get("name"),
                item_level=ranking.get("bracketData"),
                dps=ranking["amount"],
                duration_ms=ranking.get("duration"),
                report=ranking["report"]["code"],
                fight_id=ranking["report"]["fightID"],
                fight_gz=compress_fight(top["fight"]),
            )
        )
    return TopsSet(
        key=key,
        fetched_at=fetched_at,
        ranking_logs=tuple(tuple(log) for log in raw["ranking_logs"]),
        entries=tuple(entries),
    )


class TopsDb:
    """Os snapshots no banco (`TopsSnapshot` + `TopsLog`). Falha do banco só vai para o log:
    sem ele, a busca vai ao WCL como se não houvesse nada guardado."""

    def __init__(self, engine: Any = None) -> None:
        self._engine = engine

    def _session(self) -> Session:
        if self._engine is None:
            from app.db import engine  # o do app; os testes passam o deles

            self._engine = engine
        return Session(self._engine)

    def load(self, key: TopsKey) -> TopsSet | None:
        try:
            with self._session() as session:
                snapshot = session.get(TopsSnapshot, key.code)
                if snapshot is None:
                    return None
                logs = list(session.exec(select(TopsLog).where(TopsLog.key == key.code)))
                return _set_from_db(snapshot, logs, key)
        except SQLAlchemyError:
            logger.exception("Tops %s: falha ao ler do banco", key.code)
            return None

    def save(self, tops: TopsSet) -> None:
        """Troca o snapshot da chave numa transação só."""
        code = tops.key.code
        try:
            with self._session() as session:
                session.exec(delete(TopsLog).where(TopsLog.key == code))
                session.exec(delete(TopsSnapshot).where(TopsSnapshot.key == code))
                session.add(
                    TopsSnapshot(
                        key=code,
                        fetched_at=tops.fetched_at,
                        info={"ranking_logs": [list(log) for log in tops.ranking_logs]},
                    )
                )
                session.flush()  # o snapshot antes dos tops (chave estrangeira)
                for entry in tops.entries:
                    session.add(
                        TopsLog(
                            key=code, rank=entry.rank, meta=entry.meta(), fight_gz=entry.fight_gz
                        )
                    )
                session.commit()
        except SQLAlchemyError:
            logger.exception("Tops %s: falha ao gravar no banco", code)


# Um de cada por processo. Os testes limpam com `.clear()`.
tops_store = FightDataStore(ReportCache(ttl_s=TOPS_MEMORY_TTL_S, max_items=TOPS_MEMORY_MAX))
brackets_cache = ReportCache(ttl_s=BRACKETS_TTL_S, max_items=32)
tops_fill_limiter = ClientLimiter(
    global_max_calls=TOPS_FILL_LIMIT, global_window_s=TOPS_FILL_WINDOW_S
)

# Uma thread só: as buscas de tops são longas e não podem tirar a vez da pré-busca das
# lutas (que tem as threads dela) nem gastar pontos em paralelo.
_tops_executor: ThreadPoolExecutor | None = None
_tops_lock = threading.Lock()
_pending: set[tuple[Any, ...]] = set()


def tops_executor() -> ThreadPoolExecutor:
    global _tops_executor
    with _tops_lock:
        if _tops_executor is None:
            _tops_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tops")
        return _tops_executor


def shutdown_tops() -> None:
    """Desliga a fila dos tops (desligamento do app e testes): a da fila é cancelada e a que
    está baixando para na próxima página (`stop_shared_client`, chamado antes)."""
    global _tops_executor
    with _tops_lock:
        executor, _tops_executor = _tops_executor, None
        _pending.clear()
    if executor is not None:
        executor.shutdown(wait=True, cancel_futures=True)


class WclTopsSource:
    def __init__(
        self,
        client_factory: Callable[[], WclClient] = shared_client,
        store: FightDataStore | None = None,
        brackets: ReportCache | None = None,
        db: TopsDb | None = None,
        executor_factory: Callable[[], Executor] = tops_executor,
        limiter: ClientLimiter | None = None,
        cooldown: WclCooldown | None = None,
        sample: SampleTopsSource | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._client_factory = client_factory
        self._store = tops_store if store is None else store
        self._brackets = brackets_cache if brackets is None else brackets
        self._db = TopsDb() if db is None else db
        self._executor_factory = executor_factory
        self._limiter = tops_fill_limiter if limiter is None else limiter
        self._cooldown = wcl_cooldown if cooldown is None else cooldown
        self._sample = SampleTopsSource() if sample is None else sample
        self._clock = clock

    def get_tops(
        self,
        encounter_id: int,
        difficulty: int,
        item_level: float,
        own: Own,
        prefetch: bool = False,
    ) -> TopsComparison:
        """`prefetch`: chamada da fila; aí cada bracket novo no WCL passa pelo teto do
        processo (`tops_fill_limiter`), e acima dele a busca para (`PrefetchLimitError`)."""
        try:
            low, high, index = self._bracket(encounter_id, item_level)
            bracket = self._snapshot(TopsKey(encounter_id, difficulty, index), prefetch)
            return _comparison(
                bracket,
                low,
                high,
                own,
                lambda: self._snapshot(TopsKey(encounter_id, difficulty, None), prefetch),
            )
        except SourceUnavailableError as exc:
            # Plano B da demo: o bracket do kill de referência tem cópia local. Fora dele,
            # vale o erro do WCL (tentar de novo depois resolve).
            try:
                return self._sample.get_tops(encounter_id, difficulty, item_level, own)
            except TopsNotAvailableError:
                raise exc from None

    def prefetch_tops(
        self, encounter_id: int, difficulty: int, item_level: float, own: Own
    ) -> None:
        request = (encounter_id, difficulty, int(item_level), tuple(own))
        with _tops_lock:
            if request in _pending:
                return
            _pending.add(request)
        try:
            self._executor_factory().submit(self._prefetch_job, request)
        except RuntimeError:  # executor desligado (app saindo)
            with _tops_lock:
                _pending.discard(request)

    def _prefetch_job(self, request: tuple[Any, ...]) -> None:
        encounter_id, difficulty, item_level, own = request
        try:
            self.get_tops(encounter_id, difficulty, item_level, own, prefetch=True)
        except PrefetchLimitError:
            logger.info("Pré-busca dos tops %s parada: teto de brackets por hora", request)
        except (SourceUnavailableError, TopsNotAvailableError) as exc:
            logger.warning("Pré-busca dos tops %s falhou: %r", request, exc)
        except Exception:
            logger.exception("Pré-busca dos tops %s falhou com erro inesperado", request)
        finally:
            with _tops_lock:
                _pending.discard(request)

    # --- partes ---

    def _ask_wcl(self, what: str, fetch: Callable[[WclClient], Any]) -> Any:
        """Uma busca no WCL com a pausa do processo e os erros da fonte."""
        blocked = self._cooldown.active()
        if blocked is not None:
            raise SourceUnavailableError(what, *blocked)
        try:
            return fetch(self._client_factory())
        except (WclUnavailableError, httpx.HTTPError) as exc:
            if _heavy_fetch_pauses(exc):
                self._cooldown.fail(exc)
            logger.warning("Tops %s: sem resposta do Warcraft Logs: %s", what, exc)
            raise SourceUnavailableError(
                what,
                getattr(exc, "user_message", UNAVAILABLE_MESSAGE),
                getattr(exc, "error_code", WCL_UNAVAILABLE_CODE),
            ) from exc
        except WclError as exc:
            # Encontro sem ranking, consulta recusada: não há tops, e tentar de novo não muda.
            raise TopsNotAvailableError(f"Tops {what}: {exc}") from exc

    def _bracket(self, encounter_id: int, item_level: float) -> tuple[int, int, int]:
        brackets = self._brackets.get(encounter_id)
        if brackets is None:
            brackets = self._ask_wcl(
                f"brackets {encounter_id}", lambda wcl: fetch_brackets(wcl, encounter_id)
            )
            self._brackets.put(encounter_id, brackets)
        index = bracket_index(item_level, brackets["min"], brackets["bucket"])
        low, high = bracket_range(index, brackets["min"], brackets["bucket"])
        return low, high, index

    def _snapshot(self, key: TopsKey, prefetch: bool) -> TopsSet:
        try:
            return self._store.get(key, lambda: self._fill(key, prefetch), wait_s=TOPS_WAIT_S)
        except PrefetchLimitError:
            if prefetch:
                raise
            # Esperou uma pré-busca que parou no teto: a análise busca ela mesma.
            return self._store.get(key, lambda: self._fill(key, False), wait_s=TOPS_WAIT_S)

    def _fill(self, key: TopsKey, prefetch: bool) -> tuple[TopsSet, bool]:
        """Banco (se tem menos de 24 h) ou WCL. Devolve (tops, pode guardar na memória?)."""
        saved = self._db.load(key)
        if saved is not None and self._clock() - saved.fetched_at < TOPS_TTL_S:
            return saved, True
        if prefetch and self._cooldown.active() is None and not self._limiter.take(None):
            raise PrefetchLimitError(key.code)
        class_name, spec_name = ARCANE
        try:
            raw = self._ask_wcl(
                key.code,
                lambda wcl: fetch_tops(
                    wcl, key.encounter_id, class_name, spec_name, key.difficulty, key.bracket
                ),
            )
        except SourceUnavailableError:
            if saved is None:
                raise
            # Vencido, mas melhor que nada com o WCL fora do ar; não vai para a memória.
            return replace(saved, stale=True), False
        for skipped in raw["skipped"]:
            logger.info("Tops %s: luta pulada (%s)", key.code, skipped["reason"])
        if not raw["tops"]:
            raise TopsNotAvailableError(f"Ranking {key.code} sem nenhuma luta que abra.")
        tops = _set_from_wcl(key, raw, self._clock())
        self._db.save(tops)
        return tops, True


def get_tops_source() -> TopsSource:
    if get_settings().data_source == "wcl":
        return WclTopsSource()
    return SampleTopsSource()
