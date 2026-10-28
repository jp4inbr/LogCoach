"""De onde vêm os dados do relatório e da análise.

O resto do backend depende só das duas interfaces abaixo (o "D" do SOLID, item 7).
`get_report_source()` escolhe pela variável DATA_SOURCE: "wcl" lê o report da API do
Warcraft Logs; "exemplo" lê os arquivos montados à mão em `app/samples/` (plano B da
demo sem internet e fonte do CI). O "wcl" usa um cliente só por processo e guarda cada
report por alguns minutos (`ReportCache`). O analisador ainda é o de exemplo até o motor
(frente C) ficar pronto; aí basta trocá-lo em `get_analyzer`.
"""

import json
import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
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
from app.wcl.fetch import fetch_report

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
    def get_report(self, code: str) -> ReportResolved: ...


class Analyzer(Protocol):
    def analyze(
        self, report: ReportResolved, fight: FightOption, player: PlayerOption
    ) -> AnalysisResult: ...


def _load(name: str) -> dict:
    return json.loads((SAMPLES_DIR / name).read_text(encoding="utf-8"))


class SampleReportSource:
    """Devolve só o relatório de exemplo; qualquer outro código não está disponível."""

    def get_report(self, code: str) -> ReportResolved:
        if code != SAMPLE_REPORT_CODE:
            raise ReportNotAvailableError(code)
        return ReportResolved.model_validate(_load(f"report_{code}.json"))


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


def _is_arcane_mage(actor: dict[str, Any], details: dict[str, Any] | None) -> bool:
    if actor.get("subType") != ARCANE[0] or not details:
        return False
    return any(s.get("spec") == ARCANE[1] for s in details.get("specs") or [])


def build_report(
    raw: dict[str, Any],
    encounters: dict[int, dict[str, Any]] | None = None,
    npc_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Converte a saída de `wcl.fetch.fetch_report` no formato de `ReportResolved`.

    Só entram Magos Arcanos. O playerDetails é do report inteiro, então spec e item
    level são os da noite (maxItemLevel); o motor confere de novo na luta escolhida.
    """
    encounters = supported_encounters() if encounters is None else encounters
    npc_names = npc_names_pt() if npc_names is None else npc_names

    arcanes: dict[int, dict[str, Any]] = {}
    for actor in raw["actors"]:
        details = raw["details"].get(actor["id"])
        if _is_arcane_mage(actor, details):
            item_level = details.get("maxItemLevel")
            arcanes[actor["id"]] = {
                "actor_id": actor["id"],
                "name": actor["name"],
                "server": actor.get("server"),
                "spec": ARCANE_LABEL,
                "item_level": int(item_level) if item_level is not None else None,
            }

    fights = []
    for fight in raw["fights"]:
        duration_s = round((fight["endTime"] - fight["startTime"]) / 1000, 1)
        encounter_id = fight["encounterID"]
        encounter = encounters.get(encounter_id)
        difficulty = fight.get("difficulty")
        # Mesma ordem da rota /analyses: primeiro a duração, depois o chefe.
        if duration_s < MIN_FIGHT_S:
            reason = SHORT_FIGHT_REASON
        elif encounter is None:
            reason = UNSUPPORTED_BOSS_REASON
        elif encounter["difficulties"] and difficulty not in encounter["difficulties"]:
            reason = UNSUPPORTED_DIFFICULTY_REASON
        else:
            reason = None
        players = [arcanes[pid] for pid in fight.get("friendlyPlayers") or [] if pid in arcanes]
        fights.append(
            {
                "id": fight["id"],
                "boss": npc_names.get((encounter or {}).get("boss_npc_id"), fight["name"]),
                "difficulty": DIFFICULTIES.get(difficulty, f"Dificuldade {difficulty}"),
                "kill": bool(fight.get("kill")),
                "duration_s": duration_s,
                "supported": reason is None,
                "unsupported_reason": reason,
                "players": sorted(players, key=lambda p: (p["name"], p["server"] or "")),
            }
        )

    return {"code": raw["code"], "title": raw["title"], "sample": False, "fights": fights}


# Validade do report guardado: cobre o caminho /reports/resolve → /analyses sem esconder
# por muito tempo as lutas novas de um log ao vivo.
REPORT_CACHE_TTL_S = 5 * 60
REPORT_CACHE_MAX = 128


class ReportCache:
    """Reports já lidos do Warcraft Logs, por código, com validade curta (seguro entre threads).

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
        self._items: OrderedDict[str, tuple[float, ReportResolved]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, code: str) -> ReportResolved | None:
        with self._lock:
            item = self._items.get(code)
            if item is None:
                return None
            if self._clock() >= item[0]:
                del self._items[code]
                return None
            # Cópia: quem recebe pode mexer no objeto sem estragar o que está guardado.
            return item[1].model_copy(deep=True)

    def put(self, code: str, report: ReportResolved) -> None:
        with self._lock:
            self._items.pop(code, None)
            self._items[code] = (self._clock() + self._ttl_s, report.model_copy(deep=True))
            while len(self._items) > self._max_items:
                self._items.popitem(last=False)  # o mais antigo

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


# Um por processo, como o cliente do WCL. Os testes limpam com `report_cache.clear()`.
report_cache = ReportCache()


class WclReportSource:
    """Lê o report da API do Warcraft Logs (uma consulta por report, depois o cache)."""

    def __init__(
        self,
        client_factory: Callable[[], WclClient] = shared_client,
        cache: ReportCache | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._cache = report_cache if cache is None else cache

    def get_report(self, code: str) -> ReportResolved:
        cached = self._cache.get(code)
        if cached is not None:
            return cached
        try:
            # O cliente é do processo: não fecha aqui.
            raw = fetch_report(self._client_factory(), code)
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
                return SampleReportSource().get_report(code)
            if unavailable:
                message = getattr(exc, "user_message", UNAVAILABLE_MESSAGE)
                raise SourceUnavailableError(code, message) from exc
            # Privado ou inexistente: a API respondeu, mas sem o report.
            raise ReportNotAvailableError(code) from exc
        report = ReportResolved.model_validate(build_report(raw))
        self._cache.put(code, report)
        return report


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
