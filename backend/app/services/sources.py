"""De onde vêm os dados do relatório e da análise.

O resto do backend depende só das duas interfaces abaixo (o "D" do SOLID, item 7).
Hoje as implementações leem os arquivos de exemplo em `app/samples/`. Quando o
cliente do Warcraft Logs (frente B) e o motor (frente C) ficarem prontos, basta
criar uma implementação nova e trocá-la em `get_report_source` / `get_analyzer`.
"""

import json
from pathlib import Path
from typing import Protocol

from app.schemas import AnalysisResult, FightOption, PlayerOption, ReportResolved

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

# Kill de referência do CLAUDE.md: Nek'zali Mítico, luta 34, jogador Harmonist.
SAMPLE_REPORT_CODE = "XhrmBaYkGCAQjH2D"

# Item 8.2: lutas com menos de 60 s não são analisadas.
MIN_FIGHT_S = 60


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
    return SampleReportSource()


def get_analyzer() -> Analyzer:
    return SampleAnalyzer()
