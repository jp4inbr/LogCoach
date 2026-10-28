"""De onde vêm os dados do relatório e da análise.

O resto do backend depende só das duas interfaces abaixo (o "D" do SOLID, item 7).
`get_report_source()` escolhe pela variável DATA_SOURCE: "wcl" lê o report da API do
Warcraft Logs; "exemplo" lê os arquivos montados à mão em `app/samples/` (plano B da
demo sem internet e fonte do CI). O "wcl" usa um cliente só por processo: ao colar o link
busca só a lista de lutas (consulta leve) e, na luta escolhida, os Magos Arcanos dela; os
dois ficam em cache (`ReportCache`), e "Atualizar lutas" busca a lista de novo. O
analisador ainda é o de exemplo até o motor (frente C) ficar pronto; aí basta trocá-lo em
`get_analyzer`.
"""

import copy
import json
import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import httpx
import yaml

from app.config import get_settings
from app.schemas import AnalysisResult, FightOption, PlayerOption, ReportResolved
from app.wcl.client import (
    UNAVAILABLE_MESSAGE,
    WclClient,
    WclError,
    WclUnavailableError,
    shared_client,
)
from app.wcl.fetch import fetch_fight_players, fetch_report

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = APP_DIR / "samples"
ENCOUNTERS_DIR = APP_DIR / "encounters"
PT_BR_FILE = APP_DIR / "i18n" / "pt_br.yaml"

# Kill de referência do CLAUDE.md: Nek'zali Mítico, luta 34, jogador Harmonist.
SAMPLE_REPORT_CODE = "XhrmBaYkGCAQjH2D"
SAMPLE_ACTOR_ID = 455

# Item 8.2: lutas com menos de 60 s não são analisadas.
MIN_FIGHT_S = 60
SHORT_FIGHT_REASON = "A luta tem menos de 60 s. Escolha uma tentativa mais longa"
UNSUPPORTED_BOSS_REASON = "Chefe ainda não suportado"
UNSUPPORTED_DIFFICULTY_REASON = "Dificuldade ainda não suportada para esse chefe"
IN_PROGRESS_REASON = (
    "A luta ainda está subindo para o Warcraft Logs. Atualize as lutas em instantes"
)

# Dificuldades de raide no Warcraft Logs, com os nomes do cliente pt-BR.
DIFFICULTIES = {1: "Localizador", 3: "Normal", 4: "Heroico", 5: "Mítico", 10: "Mítica+"}
ARCANE = ("Mage", "Arcane")
ARCANE_LABEL = "Mago Arcano"


class ReportNotAvailableError(Exception):
    """O relatório não pôde ser aberto (privado, inexistente ou fora do exemplo)."""


class SourceUnavailableError(Exception):
    """O Warcraft Logs não atendeu (limite de pontos, fora do ar ou credenciais do servidor).

    Problema nosso ou da API, não do relatório: o usuário só precisa tentar de novo depois.
    """

    def __init__(self, code: str, user_message: str = UNAVAILABLE_MESSAGE) -> None:
        super().__init__(code)
        self.user_message = user_message


class AnalysisNotAvailableError(Exception):
    """Ainda não há análise para essa luta ou esse jogador (hoje: só o exemplo do Harmonist)."""


class ReportSource(Protocol):
    def get_report(self, code: str, refresh: bool = False) -> ReportResolved: ...

    def get_fight_players(self, code: str, fight_id: int) -> list[PlayerOption]: ...


class Analyzer(Protocol):
    def analyze(
        self, report: ReportResolved, fight: FightOption, player: PlayerOption
    ) -> AnalysisResult: ...


def _load(name: str) -> dict:
    return json.loads((SAMPLES_DIR / name).read_text(encoding="utf-8"))


class SampleReportSource:
    """Devolve só o relatório de exemplo; qualquer outro código não está disponível.

    O arquivo traz as lutas e, à parte, os Magos de cada luta suportada (`players`, por id
    da luta), como as duas consultas do Warcraft Logs. Atualizar não traz luta nova.
    """

    def _data(self, code: str) -> dict:
        if code != SAMPLE_REPORT_CODE:
            raise ReportNotAvailableError(code)
        return _load(f"report_{code}.json")

    def get_report(self, code: str, refresh: bool = False) -> ReportResolved:
        return ReportResolved.model_validate(self._data(code))

    def get_fight_players(self, code: str, fight_id: int) -> list[PlayerOption]:
        players = self._data(code).get("players", {}).get(str(fight_id), [])
        return [PlayerOption.model_validate(p) for p in players]


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


@lru_cache
def npc_names_pt() -> dict[int, str]:
    data = yaml.safe_load(PT_BR_FILE.read_text(encoding="utf-8"))
    return {int(k): v for k, v in (data.get("npcs") or {}).items()}


def _fight_reason(fight: dict[str, Any], duration_s: float, encounter: dict | None) -> str | None:
    # Luta ainda subindo (log ao vivo): a duração ainda vai mudar.
    if fight.get("inProgress"):
        return IN_PROGRESS_REASON
    # Mesma ordem da rota /analyses: primeiro a duração, depois o chefe.
    if duration_s < MIN_FIGHT_S:
        return SHORT_FIGHT_REASON
    if encounter is None:
        return UNSUPPORTED_BOSS_REASON
    if encounter["difficulties"] and fight.get("difficulty") not in encounter["difficulties"]:
        return UNSUPPORTED_DIFFICULTY_REASON
    return None


def build_report(
    raw: dict[str, Any],
    encounters: dict[int, dict[str, Any]] | None = None,
    npc_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Converte a saída de `wcl.fetch.fetch_report` no formato de `ReportResolved` (sem
    jogadores: eles vêm por luta, em `build_players`)."""
    encounters = supported_encounters() if encounters is None else encounters
    npc_names = npc_names_pt() if npc_names is None else npc_names

    fights = []
    for fight in raw["fights"]:
        duration_s = round((fight["endTime"] - fight["startTime"]) / 1000, 1)
        encounter = encounters.get(fight["encounterID"])
        difficulty = fight.get("difficulty")
        reason = _fight_reason(fight, duration_s, encounter)
        fights.append(
            {
                "id": fight["id"],
                "boss": npc_names.get((encounter or {}).get("boss_npc_id"), fight["name"]),
                "difficulty": DIFFICULTIES.get(difficulty, f"Dificuldade {difficulty}"),
                "kill": bool(fight.get("kill")),
                "duration_s": duration_s,
                "supported": reason is None,
                "unsupported_reason": reason,
            }
        )

    return {
        "code": raw["code"],
        "title": raw["title"],
        "sample": False,
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
# vivo é só a chegada de lutas novas, e essas vêm pelo botão "Atualizar lutas" (ou pelo
# /analyses, quando a luta pedida não está na lista). 6 h cobrem uma noite de raide.
REPORT_CACHE_TTL_S = 6 * 60 * 60
REPORT_CACHE_MAX = 128
PLAYERS_CACHE_MAX = 1024
# "Atualizar lutas" com a lista de agora há pouco devolve a mesma lista, sem gastar pontos
# (cliques repetidos, ou dois usuários da mesma raide ao mesmo tempo).
REFRESH_MIN_INTERVAL_S = 15


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
            # Cópia: quem recebe pode mexer no objeto sem estragar o que está guardado.
            return copy.deepcopy(item[1])

    def put(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._items.pop(key, None)
            self._items[key] = (self._clock(), copy.deepcopy(value))
            while len(self._items) > self._max_items:
                self._items.popitem(last=False)  # o mais antigo

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


# Um de cada por processo, como o cliente do WCL. Os testes limpam com `.clear()`.
report_cache = ReportCache()
players_cache = ReportCache(max_items=PLAYERS_CACHE_MAX)


class WclReportSource:
    """Lê do Warcraft Logs a lista de lutas (consulta leve) e os Magos de cada luta
    escolhida: cada um uma vez, depois do cache."""

    def __init__(
        self,
        client_factory: Callable[[], WclClient] = shared_client,
        cache: ReportCache | None = None,
        players: ReportCache | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._cache = report_cache if cache is None else cache
        self._players = players_cache if players is None else players

    def get_report(self, code: str, refresh: bool = False) -> ReportResolved:
        """Lista de lutas. `refresh` busca de novo (lutas novas de um log ao vivo); se a
        busca falhar, o que estava no cache continua lá."""
        cached = self._cache.get(code, REFRESH_MIN_INTERVAL_S if refresh else None)
        if cached is not None:
            return cached
        report, from_api = self._ask(
            code,
            lambda client: ReportResolved.model_validate(build_report(fetch_report(client, code))),
            lambda: SampleReportSource().get_report(code),
        )
        if from_api:
            self._cache.put(code, report)
        return report

    def get_fight_players(self, code: str, fight_id: int) -> list[PlayerOption]:
        """Magos Arcanos de uma luta, com spec e item level dessa luta."""
        cached = self._players.get((code, fight_id))
        if cached is not None:
            return cached
        players, from_api = self._ask(
            code,
            lambda client: [
                PlayerOption.model_validate(p)
                for p in build_players(fetch_fight_players(client, code, fight_id))
            ],
            lambda: SampleReportSource().get_fight_players(code, fight_id),
        )
        if from_api:
            self._players.put((code, fight_id), players)
        return players

    def _ask(
        self, code: str, fetch: Callable[[WclClient], Any], sample: Callable[[], Any]
    ) -> tuple[Any, bool]:
        """Uma consulta ao WCL com os erros da fonte. Devolve (valor, veio da API?): o plano
        B do exemplo não entra no cache, para não "grudar" quando a API voltar."""
        try:
            # O cliente é do processo: não fecha aqui.
            return fetch(self._client_factory()), True
        except (WclError, httpx.HTTPError) as exc:
            unavailable = isinstance(exc, (WclUnavailableError, httpx.HTTPError))
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
                raise SourceUnavailableError(code, message) from exc
            # Privado ou inexistente: a API respondeu, mas sem o report.
            raise ReportNotAvailableError(code) from exc


# --- Análise ------------------------------------------------------------------


class SampleAnalyzer:
    """Devolve o resultado de exemplo da luta de referência, só para o jogador do exemplo."""

    def analyze(
        self, report: ReportResolved, fight: FightOption, player: PlayerOption
    ) -> AnalysisResult:
        path = SAMPLES_DIR / f"analysis_{report.code}_{fight.id}.json"
        if not path.exists():
            raise AnalysisNotAvailableError(f"{report.code}/{fight.id}")
        result = AnalysisResult.model_validate(_load(path.name))
        # Outro Arcano da mesma luta (até um homônimo de outro reino) não pode receber a
        # análise do Harmonist: o jogador foi escolhido pelo actor_id na rota.
        if player.actor_id != SAMPLE_ACTOR_ID:
            raise AnalysisNotAvailableError(f"{report.code}/{fight.id}/{player.name}")
        fill_real_names(result, get_settings().names_file)
        return result


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


def get_analyzer() -> Analyzer:
    return SampleAnalyzer()
