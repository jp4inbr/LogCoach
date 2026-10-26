"""De onde vêm os dados do relatório e da análise.

O resto do backend depende só das duas interfaces abaixo (o "D" do SOLID, item 7).
`get_report_source()` escolhe pela variável DATA_SOURCE: "wcl" lê o report da API do
Warcraft Logs; "exemplo" lê os arquivos montados à mão em `app/samples/` (plano B da
demo sem internet e fonte do CI). O analisador ainda é o de exemplo até o motor
(frente C) ficar pronto; aí basta trocá-lo em `get_analyzer`.
"""

import json
import logging
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import httpx
import yaml

from app.config import get_settings
from app.schemas import AnalysisResult, FightOption, PlayerOption, ReportResolved
from app.wcl.client import WclClient, WclError
from app.wcl.fetch import fetch_report

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = APP_DIR / "samples"
ENCOUNTERS_DIR = APP_DIR / "encounters"
PT_BR_FILE = APP_DIR / "i18n" / "pt_br.yaml"

# Kill de referência do CLAUDE.md: Nek'zali Mítico, luta 34, jogador Harmonist.
SAMPLE_REPORT_CODE = "XhrmBaYkGCAQjH2D"

# Item 8.2: lutas com menos de 60 s não são analisadas.
MIN_FIGHT_S = 60
SHORT_FIGHT_REASON = "A luta tem menos de 60 s. Escolha uma tentativa mais longa"
UNSUPPORTED_BOSS_REASON = "Chefe ainda não suportado"

# Dificuldades de raide no Warcraft Logs, com os nomes do cliente pt-BR.
DIFFICULTIES = {3: "Normal", 4: "Heroico", 5: "Mítico"}
ARCANE = ("Mage", "Arcane")
ARCANE_LABEL = "Mago Arcano"


class ReportNotAvailableError(Exception):
    """O relatório não pôde ser aberto (privado, inexistente ou fora do exemplo)."""


class AnalysisNotAvailableError(Exception):
    """Ainda não há como analisar essa luta (sem dados de exemplo para ela)."""


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
def supported_encounters() -> dict[int, int | None]:
    """Encontros com regras em app/encounters/: id do encontro → NPC do chefe."""
    encounters: dict[int, int | None] = {}
    for path in sorted(ENCOUNTERS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        encounters[int(data["encounter_id"])] = data.get("boss_npc_id")
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
    encounters: dict[int, int | None] | None = None,
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
                "name": actor["name"],
                "server": actor.get("server"),
                "spec": ARCANE_LABEL,
                "item_level": int(item_level) if item_level is not None else None,
            }

    fights = []
    for fight in raw["fights"]:
        duration_s = round((fight["endTime"] - fight["startTime"]) / 1000, 1)
        encounter_id = fight["encounterID"]
        boss_npc = encounters.get(encounter_id)
        # Mesma ordem da rota /analyses: primeiro a duração, depois o chefe.
        if duration_s < MIN_FIGHT_S:
            reason = SHORT_FIGHT_REASON
        elif encounter_id not in encounters:
            reason = UNSUPPORTED_BOSS_REASON
        else:
            reason = None
        players = [arcanes[pid] for pid in fight.get("friendlyPlayers") or [] if pid in arcanes]
        difficulty = fight.get("difficulty")
        fights.append(
            {
                "id": fight["id"],
                "boss": npc_names.get(boss_npc, fight["name"]),
                "difficulty": DIFFICULTIES.get(difficulty, f"Dificuldade {difficulty}"),
                "kill": bool(fight.get("kill")),
                "duration_s": duration_s,
                "supported": reason is None,
                "unsupported_reason": reason,
                "players": sorted(players, key=lambda p: (p["name"], p["server"] or "")),
            }
        )

    return {"code": raw["code"], "title": raw["title"], "sample": False, "fights": fights}


class WclReportSource:
    """Lê o report da API do Warcraft Logs (uma consulta por report)."""

    def __init__(self, client_factory: Callable[[], WclClient] = WclClient.from_env) -> None:
        self._client_factory = client_factory

    def get_report(self, code: str) -> ReportResolved:
        try:
            with self._client_factory() as client:
                raw = fetch_report(client, code)
        except (WclError, httpx.HTTPError) as exc:
            # Privado, inexistente, sem credenciais ou API fora do ar: para o usuário é igual.
            logger.warning("Report %s indisponível no Warcraft Logs: %s", code, exc)
            raise ReportNotAvailableError(code) from exc
        return ReportResolved.model_validate(build_report(raw))


# --- Análise ------------------------------------------------------------------


class SampleAnalyzer:
    """Devolve o resultado de exemplo da luta de referência."""

    def analyze(
        self, report: ReportResolved, fight: FightOption, player: PlayerOption
    ) -> AnalysisResult:
        path = SAMPLES_DIR / f"analysis_{report.code}_{fight.id}.json"
        if not path.exists():
            raise AnalysisNotAvailableError(f"{report.code}/{fight.id}")
        return AnalysisResult.model_validate(_load(path.name))


def get_report_source() -> ReportSource:
    if get_settings().data_source == "wcl":
        return WclReportSource()
    return SampleReportSource()


def get_analyzer() -> Analyzer:
    return SampleAnalyzer()
