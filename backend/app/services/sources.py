"""De onde vêm os dados do relatório e da análise.

O resto do backend depende só das duas interfaces abaixo (o "D" do SOLID, item 7).
`get_report_source()` escolhe pela variável DATA_SOURCE: "wcl" lê o report da API do
Warcraft Logs; "exemplo" lê os arquivos montados à mão em `app/samples/` (plano B da
demo sem internet e fonte do CI). O "wcl" usa um cliente só por processo: ao colar o link
(e em "Atualizar lutas") busca só a lista de lutas (consulta leve) e, na luta escolhida, os
Magos Arcanos dela; os dois ficam em cache (`ReportCache`). Quando o jogador fica definido,
a pré-busca baixa em segundo plano os eventos da luta dele (`FightDataStore`), que o motor
lê com `get_fight_data`; a pré-busca tem limite por cliente e um teto do processo
(`prefetch_limiter`). Uma falha do Warcraft Logs fica lembrada por alguns segundos (ou pelo
`Retry-After` do limite de pedidos) e, nesse tempo, nenhuma consulta vai à API
(`WclCooldown`). Cada cliente (conta ou IP) tem um limite de consultas que vão mesmo à API
(`query_limiter`); cache não conta. O analisador é o do motor (`EngineAnalyzer`, em
`services/analyzer.py`), nos dois modos: lê os eventos daqui e os tops de `services/tops.py`.
O modo exemplo tem os eventos do kill de referência (`app/samples/fight_*.json.gz`) e os
tops do bracket dele (`app/samples/tops/`).
"""

import copy
import gzip
import json
import logging
import math
import re
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable, Hashable
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple, Protocol

import httpx
import yaml

from app.config import get_settings
from app.engine.names import npc_names as pt_br_npc_names
from app.schemas import (
    AnalysisResult,
    FightOption,
    FightReasonCode,
    PlayerOption,
    PrefetchState,
    ReportResolved,
)
from app.wcl.client import (
    TIMEOUT_MESSAGE,
    UNAVAILABLE_MESSAGE,
    WCL_UNAVAILABLE_CODE,
    WclClient,
    WclError,
    WclUnavailableError,
    rate_limit_message,
    shared_client,
)
from app.wcl.fetch import FightNotFoundError as WclFightNotFoundError
from app.wcl.fetch import fetch_fight, fetch_fight_players, fetch_report
from app.wcl.players import PlayerNotFoundError as WclPlayerNotFoundError

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = APP_DIR / "samples"
ENCOUNTERS_DIR = APP_DIR / "encounters"

# Kill de referência do CLAUDE.md: Nek'zali Mítico, luta 34, jogador Harmonist.
SAMPLE_REPORT_CODE = "XhrmBaYkGCAQjH2D"
SAMPLE_ACTOR_ID = 455

# Item 8.2: lutas com menos de 60 s não são analisadas.
MIN_FIGHT_S = 60
# Log ao vivo: nada novo há 10 min = uploader parado; uma luta ou uma M+ em andamento manda
# dados o tempo todo.
LIVE_WINDOW_S = 10 * 60

# Dificuldades de raide no Warcraft Logs, com os nomes do cliente pt-BR.
DIFFICULTIES = {1: "Localizador", 3: "Normal", 4: "Heroico", 5: "Mítico", 10: "Mítica+"}
ARCANE = ("Mage", "Arcane")
ARCANE_LABEL = "Mago Arcano"


class ReportNotAvailableError(Exception):
    """O relatório não pôde ser aberto (privado, inexistente, arquivado ou fora do exemplo).

    `archived`: o Warcraft Logs arquivou o relatório (a rota explica isso em vez de pedir
    para conferir se ele é público).
    """

    def __init__(self, code: str, archived: bool = False) -> None:
        super().__init__(code)
        self.archived = archived


class FightNotFoundError(Exception):
    """O relatório existe, mas não tem a luta pedida."""


class PlayerNotFoundError(Exception):
    """O jogador pedido não está no relatório."""


class SourceUnavailableError(Exception):
    """O Warcraft Logs não atendeu (limite de pontos, fora do ar) ou o erro é nosso (consulta
    com defeito, credenciais do servidor).

    Não é do relatório. `code` é o código do report; `user_message` e `error_code` vêm do
    cliente do WCL, que sabe a causa: "wcl_unavailable" (tentar de novo depois resolve) ou
    "unexpected_error" (só resolve corrigindo o LogCoach).
    """

    def __init__(
        self,
        code: str,
        user_message: str = UNAVAILABLE_MESSAGE,
        error_code: str = WCL_UNAVAILABLE_CODE,
    ) -> None:
        super().__init__(code)
        self.user_message = user_message
        self.error_code = error_code


class PrefetchLimitError(Exception):
    """O cliente passou do limite de pré-buscas novas (`prefetch_limiter`)."""


QUERY_LIMIT_CODE = "query_limit"


def query_limit_message(wait_s: float) -> str:
    minutes = max(1, math.ceil(wait_s / 60))
    return (
        "Você fez muitas consultas ao Warcraft Logs em pouco tempo. Para o LogCoach não "
        "estourar o limite de uso da API deles, cada pessoa pode fazer "
        f"{QUERY_LIMIT} a cada {QUERY_WINDOW_S // 60} minutos. Tente de novo em {minutes} min."
    )


class QueryLimitError(Exception):
    """O cliente passou do limite de consultas que vão à API (`query_limiter`).

    `wait_s`: segundos até a consulta mais antiga dele sair da janela.
    """

    def __init__(self, code: str, wait_s: float) -> None:
        super().__init__(code)
        self.wait_s = wait_s
        self.user_message = query_limit_message(wait_s)
        self.error_code = QUERY_LIMIT_CODE


class AnalysisNotAvailableError(Exception):
    """O motor não sabe analisar essa luta: chefe sem regras, luta sem ids do encontro,
    jogador sem item level, sem eventos (modo exemplo) ou sem tops (`TopsNotAvailableError`)."""


class FightDataNotAvailableError(AnalysisNotAvailableError):
    """Sem os eventos da luta no modo exemplo (só há a fixture do kill de referência)."""


class ReportSource(Protocol):
    """`client` (conta ou IP, de `request_client`) conta no limite de consultas por cliente
    (`QueryLimitError`) quando a consulta vai mesmo ao Warcraft Logs."""

    def get_report(
        self, code: str, refresh: bool = False, client: Hashable | None = None
    ) -> ReportResolved: ...

    def get_fight_players(
        self, code: str, fight_id: int, client: Hashable | None = None
    ) -> list[PlayerOption]: ...

    def get_fight_data(self, code: str, fight_id: int, actor_id: int) -> dict[str, Any]:
        """Luta completa do jogador, no formato de `wcl.fetch.fetch_fight` (item 12.8)."""
        ...

    def prefetch(
        self, code: str, fight_id: int, actor_id: int, client: Hashable | None = None
    ) -> PrefetchState:
        """Começa a baixar o `get_fight_data` em segundo plano, sem esperar.

        `client` (usuário logado ou IP) limita as pré-buscas de quem pediu: uma só na fila
        por cliente e no máximo `PREFETCH_LIMIT` novas por janela, com o teto do processo
        de `PREFETCH_GLOBAL_LIMIT` por hora (`PrefetchLimitError`).
        """
        ...


class Analyzer(Protocol):
    """Monta o resultado de uma luta: o `EngineAnalyzer` (services/analyzer.py), do motor.

    Ele lê os eventos com `source.get_fight_data(report.code, fight.id, player.actor_id)` (a
    fonte entra pelo construtor, em `get_analyzer`) e os tops com `TopsSource.get_tops`. Erros:
    os das fontes (`SourceUnavailableError`, `QueryLimitError`) ou `AnalysisNotAvailableError`.
    A luta completa custa ~19 pontos do Warcraft Logs (item 12.8), mas em geral já estará no
    cache: a tela chama a pré-busca (`POST /reports/{code}/fights/{id}/prefetch`) assim que o
    jogador fica definido. Se ela estiver baixando, o motor espera essa mesma busca terminar;
    se ainda estiver na fila (atrás de outras), o motor busca ele mesmo, sem esperar a fila.
    """

    def analyze(
        self, report: ReportResolved, fight: FightOption, player: PlayerOption
    ) -> AnalysisResult: ...


def _load(name: str) -> dict:
    return json.loads((SAMPLES_DIR / name).read_text(encoding="utf-8"))


def sample_fight_file(code: str, fight_id: int, actor_id: int) -> Path:
    """Eventos de exemplo de uma luta em app/samples/ (hoje só o kill de referência).

    Cópia da fixture anonimizada do save_fixtures.py (tests/fixtures/<bracket>/), que fica
    aqui dentro para o plano B ir junto com o app num deploy (o pacote é só `app*`).
    """
    return SAMPLES_DIR / f"fight_{code}_{fight_id}_{actor_id}.json.gz"


class SampleReportSource:
    """Devolve só o relatório de exemplo; qualquer outro código não está disponível.

    O arquivo traz as lutas e, à parte, os Magos de cada luta suportada (`players`, por id
    da luta), como as duas consultas do Warcraft Logs. Atualizar não traz luta nova.
    """

    def _data(self, code: str) -> dict:
        if code != SAMPLE_REPORT_CODE:
            raise ReportNotAvailableError(code)
        return _load(f"report_{code}.json")

    def get_report(
        self, code: str, refresh: bool = False, client: Hashable | None = None
    ) -> ReportResolved:
        # Arquivo local: nada ao vivo nem pausado, e nada conta no limite de consultas.
        return ReportResolved.model_validate(self._data(code))

    def get_fight_players(
        self, code: str, fight_id: int, client: Hashable | None = None
    ) -> list[PlayerOption]:
        players = self._data(code).get("players", {}).get(str(fight_id), [])
        return [PlayerOption.model_validate(p) for p in players]

    def get_fight_data(self, code: str, fight_id: int, actor_id: int) -> dict[str, Any]:
        """Os eventos de exemplo do kill de referência (luta 34, Harmonist)."""
        self._data(code)  # outro código: ReportNotAvailableError
        path = sample_fight_file(code, fight_id, actor_id)
        if not path.exists():
            raise FightDataNotAvailableError(
                f"Sem eventos de exemplo para o ator {actor_id} da luta {fight_id} de {code}: "
                "só o kill de referência tem (scripts/save_fixtures.py)."
            )
        data = json.loads(gzip.decompress(path.read_bytes()))
        owner = data["player"]["actor"]["id"]
        if owner != actor_id:
            raise FightDataNotAvailableError(
                f"A fixture da luta {fight_id} é do ator {owner}, não do {actor_id}."
            )
        return data

    def prefetch(
        self, code: str, fight_id: int, actor_id: int, client: Hashable | None = None
    ) -> PrefetchState:
        # O arquivo é local: não há o que baixar antes (nem limite a aplicar).
        return "ready"


# --- Warcraft Logs ----------------------------------------------------------


@lru_cache
def supported_encounters() -> dict[int, dict[str, Any]]:
    """Encontros com regras em app/encounters/: id do encontro → NPC do chefe e dificuldades.

    Sem `difficulties` no YAML, vale qualquer dificuldade.
    """
    encounters: dict[int, dict[str, Any]] = {}
    for path in sorted(ENCOUNTERS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        encounters[int(data["encounter_id"])] = {
            "boss_npc_id": data.get("boss_npc_id"),
            "difficulties": data.get("difficulties"),
        }
    return encounters


def _encounter_reason(fight: dict[str, Any], encounter: dict | None) -> FightReasonCode | None:
    if encounter is None:
        return "unsupported_boss"
    if encounter["difficulties"] and fight.get("difficulty") not in encounter["difficulties"]:
        return "unsupported_difficulty"
    return None


def _fight_reason(
    fight: dict[str, Any], duration_s: float, encounter: dict | None
) -> FightReasonCode | None:
    # Luta ainda subindo (log ao vivo): chefe e dificuldade já são definitivos, a duração
    # não. Chefe sem regras não fica "subindo" (terminaria cinza do mesmo jeito) e a
    # duração parcial não vale como "curta": só a luta que seria suportada fica subindo.
    if fight.get("inProgress"):
        return _encounter_reason(fight, encounter) or "in_progress"
    # Mesma ordem da rota /analyses: primeiro a duração, depois o chefe.
    if duration_s < MIN_FIGHT_S:
        return "short"
    return _encounter_reason(fight, encounter)


def build_report(
    raw: dict[str, Any],
    encounters: dict[int, dict[str, Any]] | None = None,
    npc_names: dict[int, str] | None = None,
    now_ms: float | None = None,
) -> dict[str, Any]:
    """Converte a saída de `wcl.fetch.fetch_report` no formato de `ReportResolved` (sem
    jogadores: eles vêm por luta, em `build_players`).

    O log é ao vivo (`live`) se o último evento dele (`end_time`) chegou no máximo
    `LIVE_WINDOW_S` antes de `now_ms` (agora, por padrão). Luta que estaria subindo num log
    que parou de receber dados fica pausada (`upload_paused`), e não "subindo" para sempre.
    """
    encounters = supported_encounters() if encounters is None else encounters
    npc_names = pt_br_npc_names() if npc_names is None else npc_names
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    end_time = raw.get("end_time")
    live = end_time is not None and now_ms - end_time <= LIVE_WINDOW_S * 1000

    fights = []
    for fight in raw["fights"]:
        duration_s = round((fight["endTime"] - fight["startTime"]) / 1000, 1)
        encounter = encounters.get(fight["encounterID"])
        difficulty = fight.get("difficulty")
        code = _fight_reason(fight, duration_s, encounter)
        paused = code == "in_progress" and not live
        if paused:
            code = "upload_paused"
        fights.append(
            {
                "id": fight["id"],
                "boss": npc_names.get((encounter or {}).get("boss_npc_id"), fight["name"]),
                "difficulty": DIFFICULTIES.get(difficulty, f"Dificuldade {difficulty}"),
                "encounter_id": fight["encounterID"],
                "difficulty_id": difficulty,
                "kill": bool(fight.get("kill")),
                "duration_s": duration_s,
                "supported": code is None,
                "unsupported_code": code,
                "in_progress": code == "in_progress",
                "upload_paused": paused,
            }
        )

    return {
        "code": raw["code"],
        "title": raw["title"],
        "sample": False,
        "live": live,
        "fights": fights,
    }


def build_players(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Converte a saída de `wcl.fetch.fetch_fight_players` nos `PlayerOption` da luta.

    Só entram Magos com spec Arcano nesta luta (quem jogou Fogo nesse chefe fica de fora).
    """
    actors = {a["id"]: a for a in raw["actors"] if a.get("subType") == ARCANE[0]}
    players = []
    for entry in raw["players"]:
        actor = actors.get(entry["id"])
        if actor is None or entry.get("spec") != ARCANE[1]:
            continue
        item_level = entry.get("item_level")
        players.append(
            {
                "actor_id": actor["id"],
                "name": actor["name"],
                "server": actor.get("server"),
                "spec": ARCANE_LABEL,
                "item_level": int(item_level) if item_level else None,
            }
        )
    return sorted(players, key=lambda p: (p["name"], p["server"] or ""))


# Validade longa: luta que já subiu para o Warcraft Logs não muda; o que muda num log ao
# vivo é só a chegada de lutas novas, e essas vêm ao colar o link, no "Atualizar lutas" (ou
# no /analyses, quando a luta pedida não está na lista). 6 h cobrem uma noite de raide.
REPORT_CACHE_TTL_S = 6 * 60 * 60
REPORT_CACHE_MAX = 128
PLAYERS_CACHE_MAX = 1024
# Colar o link ou "Atualizar lutas" com a lista de agora há pouco devolve a mesma lista,
# sem gastar pontos (cliques repetidos, ou dois usuários da mesma raide ao mesmo tempo).
# Curto o bastante para quem acabou de ver a luta terminar não receber a lista de antes.
REFRESH_MIN_INTERVAL_S = 8
# Eventos de uma luta (pré-busca e motor). O kill de referência (6:55) tem ~1,3 MB de JSON
# e ocupa ~4,5 MB na memória do Python; luta longa passa disso. O cache só precisa cobrir o
# caminho "escolher a luta → analisar" (segundos ou minutos) e uma análise repetida da
# mesma luta: 8 lutas (~40–60 MB no pior caso) atendem alguns usuários ao mesmo tempo na
# versão alfa sem pesar no servidor. Validade igual à da lista: luta que subiu não muda.
FIGHT_DATA_CACHE_MAX = 8
# Quem pede uma luta que já está baixando espera ela terminar até esse limite. A luta
# completa são várias páginas de eventos (~19 pontos); cada pedido já tem o próprio timeout.
FIGHT_DATA_WAIT_S = 180
# Pré-buscas ao mesmo tempo (threads do processo). Duas bastam para a versão alfa e seguram
# o gasto de pontos e de memória se muitos escolherem luta juntos; o resto espera na fila.
PREFETCH_WORKERS = 2
# Pré-buscas novas por cliente (usuário logado ou IP) na janela: ~19 pontos cada, então 10
# em 10 min são ~190 pontos, menos de um quinto dos 1000/h do LogCoach inteiro. Quem troca
# de jogador ou de luta algumas vezes não chega perto; quem clica em tudo não esgota os
# pontos de todos.
PREFETCH_LIMIT = 10
PREFETCH_WINDOW_S = 10 * 60
# Teto do processo inteiro, somando todos os clientes: o limite por cliente não segura quem
# troca de IP (com IPv6 é fácil). 30 por hora × ~19 pontos são ~570 pontos, pouco mais da
# metade dos 1000/h do Warcraft Logs (era 40 com ~12 pontos; a luta ficou mais cara em 03/11
# com o tempo ativo, o CombatantInfo, a vida e a cura recebida). O resto fica para colar
# links, Magos de cada luta, a busca dos tops e as análises (que buscam a luta sozinhas quando
# a pré-busca não veio). A rever quando a busca dos tops entrar (passo 4.2: ~210 pontos por
# bracket novo).
PREFETCH_GLOBAL_LIMIT = 30
PREFETCH_GLOBAL_WINDOW_S = 60 * 60
# Consultas por cliente que vão mesmo ao Warcraft Logs (lista de lutas e Magos de uma luta;
# cache não conta): uma noite de raide ao vivo usa ~colar + 8 automáticas + ~10 lutas em
# 30 min; segura abuso em ~80 pontos/h por cliente, de 1000.
QUERY_LIMIT = 20
QUERY_WINDOW_S = 30 * 60
# Clientes lembrados pelo limitador: acima disso, esquece quem pediu há mais tempo.
PREFETCH_CLIENTS_MAX = 10_000
# A limpeza de quem não pede nada há uma janela roda no máximo uma vez por minuto.
PREFETCH_PRUNE_INTERVAL_S = 60
# Falha do Warcraft Logs lembrada (`WclCooldown`): nesse tempo nenhuma consulta vai à API.
# No mínimo a trava da lista; limite de pedidos sem `Retry-After` pausa 1 min (o limite de
# pontos é por hora, não adianta insistir); com `Retry-After`, o tempo dele, até 5 min (data
# absurda não para o LogCoach por horas: passado o teto, uma consulta testa a API de novo).
WCL_COOLDOWN_S = REFRESH_MIN_INTERVAL_S
WCL_RATE_LIMIT_COOLDOWN_S = 60
WCL_COOLDOWN_MAX_S = 5 * 60


class ReportCache:
    """O que já foi lido do Warcraft Logs, por chave, com validade (seguro entre threads).

    Serve para a lista de lutas (por código) e para os Magos de cada luta (código, luta).
    Só guarda o que veio da API; falhas e o plano B do exemplo não entram.
    """

    def __init__(
        self,
        ttl_s: float = REPORT_CACHE_TTL_S,
        max_items: int = REPORT_CACHE_MAX,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_s = ttl_s
        self._max_items = max_items
        self._clock = clock
        self._items: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable, max_age_s: float | None = None) -> Any:
        """O valor guardado, ou None se não há, venceu ou é mais velho que `max_age_s`."""
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            age = self._clock() - item[0]
            if age >= self._ttl_s:
                del self._items[key]
                return None
            if max_age_s is not None and age >= max_age_s:
                return None
            value = item[1]
        # Cópia, para quem recebe poder mexer no objeto sem estragar o guardado, e fora do
        # lock: os eventos de uma luta (~4,5 MB) não podem travar as outras rotas. O guardado
        # nunca é alterado, então copiar sem o lock é seguro.
        return copy.deepcopy(value)

    def has(self, key: Hashable) -> bool:
        """Se há valor válido, sem copiar (os eventos de uma luta são MB)."""
        with self._lock:
            item = self._items.get(key)
            if item is not None and self._clock() - item[0] >= self._ttl_s:
                del self._items[key]
                item = None
            return item is not None

    def put(self, key: Hashable, value: Any, copied: bool = False) -> None:
        """Guarda uma cópia de `value`, feita fora do lock. `copied`: `value` já é uma cópia
        só do cache, que ninguém mais altera."""
        stored = value if copied else copy.deepcopy(value)
        with self._lock:
            self._items.pop(key, None)
            self._items[key] = (self._clock(), stored)
            while len(self._items) > self._max_items:
                self._items.popitem(last=False)  # o mais antigo

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


Fetch = Callable[[], tuple[Any, bool]]


class FightKey(NamedTuple):
    """Chave dos eventos de uma luta no `FightDataStore`."""

    code: str
    fight_id: int
    actor_id: int


def _report_code(key: Hashable) -> str:
    # O código do report para as mensagens de erro (os testes usam chaves simples).
    return getattr(key, "code", None) or str(key)


class _Flight:
    """Uma busca de uma chave: na fila do executor (pré-busca) ou baixando."""

    __slots__ = ("future", "claimed", "job", "clients")

    def __init__(self) -> None:
        # Quem espera a busca lê daqui (só busca assumida: a da fila não tem quem espere).
        self.future: Future = Future()
        # Alguém já assumiu a busca (a thread da pré-busca ou quem precisa dos dados), ou ela
        # saiu da fila. Enquanto falso, a busca está só na fila.
        self.claimed = False
        self.job: Future | None = None  # a tarefa no executor, enquanto está na fila
        self.clients: set[Hashable] = set()  # quem pediu essa pré-busca, enquanto na fila


class FightDataStore:
    """Eventos de luta já baixados (cache) e os que estão baixando agora (single-flight).

    Uma busca por chave de cada vez: quem pede o que já está baixando espera essa busca em
    vez de baixar de novo. A pré-busca que ainda está na fila (atrás de outras) não segura
    ninguém: quem precisa dos dados assume a busca e baixa na hora. Cada cliente tem no
    máximo uma pré-busca na fila; uma nova dele tira a anterior da fila. Falha não entra no
    cache (o próximo pedido tenta de novo); quem estava esperando recebe o mesmo erro. Só se
    espera busca assumida: a que sai da fila sem rodar não tem a quem avisar.
    """

    def __init__(self, cache: ReportCache | None = None) -> None:
        self._cache = ReportCache(max_items=FIGHT_DATA_CACHE_MAX) if cache is None else cache
        self._running: dict[Hashable, _Flight] = {}
        self._queued: dict[Hashable, Hashable] = {}  # cliente → chave da pré-busca na fila
        self._lock = threading.Lock()

    def get(self, key: Hashable, fetch: Fetch, wait_s: float = FIGHT_DATA_WAIT_S) -> Any:
        """O valor do cache, o da busca em andamento ou o de uma busca nova (nesta thread).

        `fetch` devolve (valor, pode guardar?): o plano B do exemplo não entra no cache.
        """
        while True:
            value = self._cache.get(key)
            if value is not None:
                return value
            job = None
            with self._lock:
                flight = self._running.get(key)
                if flight is None:
                    if self._cache.has(key):
                        continue  # entrou no cache entre a leitura e o lock: lê de novo
                    flight = self._running[key] = _Flight()
                    flight.claimed = owner = True
                elif not flight.claimed:
                    # Pré-busca ainda na fila: busca aqui, sem esperar as que estão na frente.
                    job = self._claim(key, flight)
                    owner = True
                else:
                    owner = False
            if owner:
                if job is not None:
                    job.cancel()  # libera o lugar na fila (fora do lock: chama o callback)
                return self._run(key, flight, fetch)
            try:
                return copy.deepcopy(flight.future.result(timeout=wait_s))
            except TimeoutError:
                raise SourceUnavailableError(_report_code(key), TIMEOUT_MESSAGE) from None

    def start(
        self,
        key: Hashable,
        fetch: Fetch,
        executor: Executor,
        client: Hashable | None = None,
        admit: Callable[[], bool] | None = None,
    ) -> PrefetchState:
        """Põe a busca na fila do executor, se ela não está no cache nem baixando.

        `admit` é chamado só quando a busca seria nova ("ready" e "running" não gastam
        pontos); se ele negar, levanta `PrefetchLimitError` sem mexer em nada.
        """
        with self._lock:
            if self._cache.has(key):
                # Já no cache: nada a buscar, mas a pré-busca anterior desse cliente sai da
                # fila, como quando ele pede uma luta nova.
                state: PrefetchState = "ready"
            else:
                flight = self._running.get(key)
                if flight is None and admit is not None and not admit():
                    raise PrefetchLimitError(_report_code(key))
                state = "running" if flight is not None else "started"
            dropped = self._leave_queue(client, key)
            if state == "running":
                self._join_queue(client, key, flight)
            elif state == "started":
                flight = self._running[key] = _Flight()
                self._join_queue(client, key, flight)
        if dropped is not None:
            dropped.cancel()
        if state != "started":
            return state
        try:
            job = executor.submit(self._background, key, flight, fetch)
        except RuntimeError:  # executor já desligado (app saindo)
            with self._lock:
                if not flight.claimed:  # se alguém já assumiu, a busca é dele
                    self._claim(key, flight)
                    self._forget(key, flight)
            raise
        with self._lock:
            # Alguém pode ter assumido (ou tirado da fila) antes de a tarefa existir.
            cancel = flight.claimed
            if not cancel:
                flight.job = job
        if cancel:
            job.cancel()
        else:
            job.add_done_callback(lambda done: self._job_done(key, flight, done))
        return state

    def _join_queue(self, client: Hashable | None, key: Hashable, flight: _Flight) -> None:
        if client is not None and not flight.claimed:
            flight.clients.add(client)
            self._queued[client] = key

    def _leave_queue(self, client: Hashable | None, key: Hashable) -> Future | None:
        """Tira o cliente da pré-busca dele que está na fila, se for de outra chave. Sem mais
        ninguém pedindo, ela sai da fila; devolve a tarefa para cancelar fora do lock."""
        old = self._queued.get(client) if client is not None else None
        if old is None or old == key:
            return None
        del self._queued[client]
        flight = self._running.get(old)
        if flight is None or flight.claimed:
            return None
        flight.clients.discard(client)
        if flight.clients:
            return None  # outro cliente também pediu essa luta
        job = self._claim(old, flight)
        self._forget(old, flight)
        return job

    def _claim(self, key: Hashable, flight: _Flight) -> Future | None:
        """Marca a busca como assumida e tira da fila (com o lock). Devolve a tarefa."""
        flight.claimed = True
        for client in flight.clients:
            if self._queued.get(client) == key:
                del self._queued[client]
        flight.clients.clear()
        job, flight.job = flight.job, None
        return job

    def _forget(self, key: Hashable, flight: _Flight) -> None:
        if self._running.get(key) is flight:
            del self._running[key]

    def _job_done(self, key: Hashable, flight: _Flight, job: Future) -> None:
        """Tarefa cancelada na fila (desligamento com `cancel_futures`): a busca sai de
        "baixando", para o próximo pedido buscar de novo. Ninguém espera busca da fila (quem
        precisa assume), então não há a quem avisar."""
        if not job.cancelled():
            return
        with self._lock:
            if flight.claimed:
                return  # alguém assumiu ou ela já saiu da fila
            self._claim(key, flight)
            self._forget(key, flight)

    def _run(self, key: Hashable, flight: _Flight, fetch: Fetch) -> Any:
        try:
            value, cacheable = fetch()
        except BaseException as exc:
            with self._lock:
                self._forget(key, flight)
            flight.future.set_exception(exc)
            raise
        # Uma cópia só do cache e de quem esperava (cada um copia de novo), feita fora do
        # lock; quem buscou fica com o original.
        stored = copy.deepcopy(value)
        with self._lock:
            # Primeiro no cache, depois sai de "baixando": quem chega no meio acha um dos dois.
            if cacheable:
                self._cache.put(key, stored, copied=True)
            self._forget(key, flight)
        flight.future.set_result(stored)
        return value

    def _background(self, key: Hashable, flight: _Flight, fetch: Fetch) -> None:
        with self._lock:
            if flight.claimed:
                return  # quem precisava dos dados já assumiu, ou ela saiu da fila
            self._claim(key, flight)
        # Na pré-busca ninguém espera a resposta: a falha só fica no log.
        try:
            self._run(key, flight, fetch)
        except (
            ReportNotAvailableError,
            FightNotFoundError,
            PlayerNotFoundError,
            SourceUnavailableError,
            AnalysisNotAvailableError,
        ) as exc:
            logger.warning("Pré-busca de %s falhou (o próximo pedido tenta de novo): %r", key, exc)
        except Exception:
            logger.exception("Pré-busca de %s falhou com erro inesperado", key)

    def clear(self) -> None:
        self._cache.clear()


def _expire(calls: deque[float], now: float, window_s: float) -> None:
    while calls and now - calls[0] >= window_s:
        calls.popleft()


class ClientLimiter:
    """Chamadas numa janela deslizante, por cliente e, com `global_max_calls`, no processo
    inteiro (em memória do processo). Os padrões são os da pré-busca (`prefetch_limiter`); o
    `query_limiter` usa `QUERY_LIMIT` por cliente, sem teto do processo.

    "Cliente" é o usuário logado ou, sem login, o IP do pedido (IPv6 agrupado por /64; atrás
    de um proxy reverso, o IP é o do proxy e todos os anônimos dividem o limite). Os clientes
    ficam na ordem da última pré-busca, para esquecer os parados sem varrer todos.
    """

    def __init__(
        self,
        max_calls: int = PREFETCH_LIMIT,
        window_s: float = PREFETCH_WINDOW_S,
        global_max_calls: int | None = PREFETCH_GLOBAL_LIMIT,
        global_window_s: float = PREFETCH_GLOBAL_WINDOW_S,
        max_clients: int = PREFETCH_CLIENTS_MAX,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_calls = max_calls
        self._window_s = window_s
        self._global_max_calls = global_max_calls
        self._global_window_s = global_window_s
        self._max_clients = max_clients
        self._clock = clock
        # Cliente → horários das pré-buscas, de quem pediu há mais tempo ao mais recente.
        self._calls: OrderedDict[Hashable, deque[float]] = OrderedDict()
        self._global: deque[float] = deque()
        self._pruned_at = clock()
        self._lock = threading.Lock()

    def take(self, client: Hashable | None) -> bool:
        """Conta uma chamada, se o cliente e o processo ainda têm. Sem cliente, só o teto do
        processo vale (sem teto, sempre pode). Negada, não conta nada."""
        global_max = self._global_max_calls
        with self._lock:
            now = self._clock()
            if now - self._pruned_at >= PREFETCH_PRUNE_INTERVAL_S:
                self._prune(now)
            _expire(self._global, now, self._global_window_s)
            if global_max is not None and len(self._global) >= global_max:
                return False
            calls = self._calls.get(client) if client is not None else None
            if calls is not None:
                _expire(calls, now, self._window_s)
                if len(calls) >= self._max_calls:
                    return False
            if global_max is not None:
                self._global.append(now)
            if client is None:
                return True
            if calls is None:
                calls = self._calls[client] = deque()
            calls.append(now)
            self._calls.move_to_end(client)
            while len(self._calls) > self._max_clients:
                self._calls.popitem(last=False)  # quem pediu há mais tempo
            return True

    def retry_in(self, client: Hashable | None) -> float:
        """Segundos até a chamada mais antiga do cliente sair da janela (0 se ele tem vaga)."""
        with self._lock:
            now = self._clock()
            # Sem alterar a fila do cliente (o `_prune` conta com ela nunca vazia).
            calls = self._calls.get(client, ()) if client is not None else ()
            recent = [t for t in calls if now - t < self._window_s]
            if len(recent) < self._max_calls:
                return 0.0
            return max(0.0, self._window_s - (now - recent[-self._max_calls]))

    def _prune(self, now: float) -> None:
        # Esquece quem não pede nada há uma janela inteira: pela ordem, são os primeiros.
        self._pruned_at = now
        while self._calls:
            calls = next(iter(self._calls.values()))
            if now - calls[-1] < self._window_s:
                break
            self._calls.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._calls.clear()
            self._global.clear()


class WclCooldown:
    """A última falha do Warcraft Logs, lembrada por um tempo (`WCL_COOLDOWN_S` ou o do limite
    de pedidos), para o processo inteiro: o limite de pontos e uma queda valem para todas as
    consultas.

    Sem isso, com a lista guardada servida, cada pedido e cada atualização automática de
    cada aba bateria no WCL de novo, e com o limite de pedidos (429) isso só prolonga o
    bloqueio. Sucesso não apaga a falha: uma consulta que já estava no ar não encerra a
    pausa pedida pelo `Retry-After`.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._until = float("-inf")
        self._message = UNAVAILABLE_MESSAGE
        self._error_code = WCL_UNAVAILABLE_CODE
        self._retry_at: float | None = None  # quando o WCL disse que libera (limite)
        self._lock = threading.Lock()

    def fail(self, exc: BaseException) -> None:
        """Lembra a falha. Fica a pausa que termina mais tarde."""
        rate_limited = bool(getattr(exc, "rate_limited", False))
        retry_after = getattr(exc, "retry_after_s", None)
        if retry_after is not None:
            wait = min(max(retry_after, WCL_COOLDOWN_S), WCL_COOLDOWN_MAX_S)
        elif rate_limited:
            wait = WCL_RATE_LIMIT_COOLDOWN_S
        else:
            wait = WCL_COOLDOWN_S
        with self._lock:
            now = self._clock()
            if now + wait < self._until:
                return
            self._until = now + wait
            self._message = getattr(exc, "user_message", UNAVAILABLE_MESSAGE)
            self._error_code = getattr(exc, "error_code", WCL_UNAVAILABLE_CODE)
            known = rate_limited and retry_after is not None
            self._retry_at = now + retry_after if known else None

    def active(self) -> tuple[str, str] | None:
        """(mensagem, código) da falha enquanto a pausa vale; None se pode chamar a API."""
        with self._lock:
            now = self._clock()
            if now >= self._until:
                return None
            message = self._message
            if self._retry_at is not None:
                # "Tente daqui a uns N minutos" conta do que falta, não do que o WCL disse.
                message = rate_limit_message(max(0.0, self._retry_at - now))
            return message, self._error_code

    def clear(self) -> None:
        with self._lock:
            self._until = float("-inf")
            self._retry_at = None


# Um de cada por processo, como o cliente do WCL. Os testes limpam com `.clear()`.
report_cache = ReportCache()
players_cache = ReportCache(max_items=PLAYERS_CACHE_MAX)
fight_data_store = FightDataStore()
prefetch_limiter = ClientLimiter()
query_limiter = ClientLimiter(QUERY_LIMIT, QUERY_WINDOW_S, global_max_calls=None)
wcl_cooldown = WclCooldown()

# Threads da pré-busca: do processo, e não o BackgroundTasks do FastAPI, porque a busca
# (dezenas de segundos) não deve ocupar as threads das rotas síncronas, não depende do
# pedido que a disparou e fica limitada a PREFETCH_WORKERS ao mesmo tempo.
_prefetch_executor: ThreadPoolExecutor | None = None
_prefetch_lock = threading.Lock()


def prefetch_executor() -> ThreadPoolExecutor:
    """O executor da pré-busca, criado no primeiro uso."""
    global _prefetch_executor
    with _prefetch_lock:
        if _prefetch_executor is None:
            _prefetch_executor = ThreadPoolExecutor(
                max_workers=PREFETCH_WORKERS, thread_name_prefix="prefetch"
            )
        return _prefetch_executor


def shutdown_prefetch() -> None:
    """Desliga o executor da pré-busca (desligamento do app e testes).

    As da fila são canceladas (com `--reload` ou SIGTERM, rodar a fila inteira levaria
    minutos) e saem do store (o próximo pedido busca de novo); ninguém espera busca da fila.
    Só as que já estão baixando (no máximo PREFETCH_WORKERS) terminam.
    """
    global _prefetch_executor
    with _prefetch_lock:
        executor, _prefetch_executor = _prefetch_executor, None
    if executor is not None:
        executor.shutdown(wait=True, cancel_futures=True)


class WclReportSource:
    """Lê do Warcraft Logs a lista de lutas (consulta leve), os Magos de cada luta escolhida
    e os eventos da luta do jogador: cada um uma vez, depois do cache."""

    def __init__(
        self,
        client_factory: Callable[[], WclClient] = shared_client,
        cache: ReportCache | None = None,
        players: ReportCache | None = None,
        fight_data: FightDataStore | None = None,
        executor_factory: Callable[[], Executor] = prefetch_executor,
        limiter: ClientLimiter | None = None,
        cooldown: WclCooldown | None = None,
        queries: ClientLimiter | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._cache = report_cache if cache is None else cache
        self._players = players_cache if players is None else players
        self._fight_data = fight_data_store if fight_data is None else fight_data
        self._executor_factory = executor_factory
        self._limiter = prefetch_limiter if limiter is None else limiter
        self._cooldown = wcl_cooldown if cooldown is None else cooldown
        self._queries = query_limiter if queries is None else queries

    def get_report(
        self, code: str, refresh: bool = False, client: Hashable | None = None
    ) -> ReportResolved:
        """Lista de lutas. `refresh` busca de novo (lutas novas de um log ao vivo).

        Se a busca falhar com o Warcraft Logs fora do ar (ou erro nosso), ou o cliente
        passar do limite de consultas, e houver lista no cache, devolve a guardada com
        `stale`, a mensagem e o código do erro: o usuário continua escolhendo a luta. Sem
        lista guardada, o erro sobe. Logo depois de uma falha (`WclCooldown`), responde assim
        sem chamar a API.
        """
        cached = self._cache.get(code, REFRESH_MIN_INTERVAL_S if refresh else None)
        if cached is not None:
            return cached
        try:
            report, from_api = self._ask(
                code,
                lambda wcl: ReportResolved.model_validate(build_report(fetch_report(wcl, code))),
                lambda: SampleReportSource().get_report(code),
                client=client,
            )
        except (SourceUnavailableError, QueryLimitError) as exc:
            stale = self._cache.get(code)
            if stale is None:
                raise
            stale.stale = True
            stale.stale_message, stale.stale_code = exc.user_message, exc.error_code
            return stale
        if from_api:
            self._cache.put(code, report)
        return report

    def get_fight_players(
        self, code: str, fight_id: int, client: Hashable | None = None
    ) -> list[PlayerOption]:
        """Magos Arcanos de uma luta, com spec e item level dessa luta.

        Lista vazia não entra no cache: logo depois da luta o WCL pode ainda não ter
        processado os dados de combate, e "nenhum Arcano" por 6 h esconderia o mago.
        """
        cached = self._players.get((code, fight_id))
        if cached is not None:
            return cached
        players, from_api = self._ask(
            code,
            lambda wcl: [
                PlayerOption.model_validate(p)
                for p in build_players(fetch_fight_players(wcl, code, fight_id))
            ],
            lambda: SampleReportSource().get_fight_players(code, fight_id),
            client=client,
        )
        if from_api and players:
            self._players.put((code, fight_id), players)
        return players

    def get_fight_data(self, code: str, fight_id: int, actor_id: int) -> dict[str, Any]:
        """Luta completa do jogador (`wcl.fetch.fetch_fight`, ~19 pontos), uma vez por
        (código, luta, jogador). Se a pré-busca dela está baixando, espera essa busca; se
        ainda está na fila, busca aqui."""
        return self._fight_data.get(
            FightKey(code, fight_id, actor_id), self._fight_fetch(code, fight_id, actor_id)
        )

    def prefetch(
        self, code: str, fight_id: int, actor_id: int, client: Hashable | None = None
    ) -> PrefetchState:
        """Põe a luta do jogador na fila de pré-busca e responde na hora."""
        return self._fight_data.start(
            FightKey(code, fight_id, actor_id),
            self._fight_fetch(code, fight_id, actor_id),
            self._executor_factory(),
            client=client,
            admit=lambda: self._admit_prefetch(code, client),
        )

    def _admit_prefetch(self, code: str, client: Hashable | None) -> bool:
        """Pré-busca nova: com o WCL falhando há pouco, o erro dele (sem gastar o limite);
        senão, o limite do cliente e o do processo."""
        blocked = self._cooldown.active()
        if blocked is not None and code != SAMPLE_REPORT_CODE:
            raise SourceUnavailableError(code, *blocked)
        return self._limiter.take(client)

    def _fight_fetch(self, code: str, fight_id: int, actor_id: int) -> Fetch:
        # Sem `client`: a pré-busca tem limite próprio e a análise, o do plano.
        return lambda: self._ask(
            code,
            lambda wcl: fetch_fight(wcl, code, fight_id, actor_id=actor_id),
            lambda: SampleReportSource().get_fight_data(code, fight_id, actor_id),
            pauses=_heavy_fetch_pauses,
        )

    def _ask(
        self,
        code: str,
        fetch: Callable[[WclClient], Any],
        sample: Callable[[], Any],
        client: Hashable | None = None,
        pauses: Callable[[BaseException], bool] | None = None,
    ) -> tuple[Any, bool]:
        """Uma consulta ao WCL com os erros da fonte. Devolve (valor, veio da API?): o plano
        B do exemplo não entra no cache, para não "grudar" quando a API voltar.

        Logo depois de uma falha do WCL (`WclCooldown`), repete essa falha sem chamar a API.
        Com `client`, a consulta que vai mesmo à API conta no limite dele (`QueryLimitError`
        quando passa); o report de exemplo não conta. `pauses` decide se uma falha do WCL
        liga a pausa (padrão: toda falha do lado dele).
        """
        blocked = self._cooldown.active()
        if blocked is not None:
            if code == SAMPLE_REPORT_CODE:
                return sample(), False
            raise SourceUnavailableError(code, *blocked)
        if client is not None and code != SAMPLE_REPORT_CODE and not self._queries.take(client):
            raise QueryLimitError(code, self._queries.retry_in(client))
        try:
            # O cliente é do processo: não fecha aqui.
            return fetch(self._client_factory()), True
        except WclFightNotFoundError as exc:
            # O report abriu, só não tem essa luta: nem "confira se é público" nem pausa.
            raise FightNotFoundError(code) from exc
        except WclPlayerNotFoundError as exc:
            raise PlayerNotFoundError(code) from exc
        except (WclError, httpx.HTTPError) as exc:
            unavailable = isinstance(exc, (WclUnavailableError, httpx.HTTPError))
            if unavailable and (pauses is None or pauses(exc)):
                self._cooldown.fail(exc)
            logger.warning(
                "Report %s %s: %s",
                code,
                "sem resposta do Warcraft Logs" if unavailable else "indisponível",
                exc,
            )
            # Plano B da demo: sem internet, o link de exemplo continua abrindo.
            if code == SAMPLE_REPORT_CODE:
                return sample(), False
            if unavailable:
                message = getattr(exc, "user_message", UNAVAILABLE_MESSAGE)
                error_code = getattr(exc, "error_code", WCL_UNAVAILABLE_CODE)
                raise SourceUnavailableError(code, message, error_code) from exc
            # Privado, inexistente ou arquivado: a API respondeu, mas sem o report.
            raise ReportNotAvailableError(code, getattr(exc, "archived", False)) from exc


def _heavy_fetch_pauses(exc: BaseException) -> bool:
    """Falha da busca pesada (eventos da luta) só pausa o processo se for o limite de pedidos
    ou 5xx do WCL: timeout ou rede numa busca de dezenas de segundos não dizem que as
    consultas leves (lista, Magos) também vão falhar."""
    status = getattr(exc, "status", None)
    return bool(getattr(exc, "rate_limited", False)) or (status is not None and status >= 500)


# --- Análise ------------------------------------------------------------------


def fill_real_names(result: AnalysisResult, names_file: Path) -> None:
    """Põe o nome real dos tops a partir do names.local.json, se ele existir na máquina (RF25).

    O arquivo é um mapa por bracket e por fixture: `{"nekzali_mythic_326_328":
    {"top01.json.gz": {"top01": {"name", "server"}}}}`. Nunca vai para o git nem para a IA.
    """
    if not names_file.exists():
        return
    names = json.loads(names_file.read_text(encoding="utf-8"))
    low, high = re.findall(r"\d+", result.comparison.bracket)[:2]
    bracket = next((v for k, v in names.items() if k.endswith(f"_{low}_{high}")), {})
    for player in result.comparison.players:
        real = bracket.get(f"{player.display_name}.json.gz", {}).get(player.display_name)
        if real:
            player.name = real.get("name")
            player.server = real.get("server")


def get_report_source() -> ReportSource:
    if get_settings().data_source == "wcl":
        return WclReportSource()
    return SampleReportSource()
