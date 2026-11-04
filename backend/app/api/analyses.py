"""Rodar uma análise e abrir o resultado (RF01, RF10, RF12, RF14)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import OptionalUserDep, SessionDep, check_plan_limit
from app.api.reports import (
    ReportSourceDep,
    call_source,
    load_fight,
    load_player,
    request_client,
)
from app.errors import api_error
from app.models import Analysis
from app.schemas import AnalysisOut, AnalysisRequest, AnalysisResult
from app.services.analyzer import get_analyzer
from app.services.sources import (
    AnalysisNotAvailableError,
    Analyzer,
    FightDataNotAvailableError,
    SampleReportSource,
)
from app.services.tops import TopsNotAvailableError

router = APIRouter(prefix="/analyses", tags=["análises"])

AnalyzerDep = Annotated[Analyzer, Depends(get_analyzer)]

NO_TOPS_MESSAGE = (
    "Ainda não há tops do Warcraft Logs para comparar com essa luta (chefe, dificuldade e "
    "faixa de item level do personagem). Tente de novo mais tarde ou escolha outra luta."
)
NOT_AVAILABLE_MESSAGE = (
    "Ainda não conseguimos analisar essa luta com esse personagem: faltam dados da luta ou "
    "o chefe ainda não tem regras no LogCoach. Nesta versão alfa, só o Nek'zali Mítico."
)
SAMPLE_FIGHT_MESSAGE = (
    "Sem conexão com o Warcraft Logs, só há os eventos do Harmonist na luta 34 do relatório "
    "de exemplo."
)


def _not_available_message(exc: AnalysisNotAvailableError, source: object) -> str:
    if isinstance(exc, TopsNotAvailableError):
        return NO_TOPS_MESSAGE
    if isinstance(exc, FightDataNotAvailableError) and isinstance(source, SampleReportSource):
        return SAMPLE_FIGHT_MESSAGE
    return NOT_AVAILABLE_MESSAGE


def _to_out(analysis: Analysis) -> AnalysisOut:
    return AnalysisOut(
        id=analysis.id,
        created_at=analysis.created_at,
        saved=analysis.user_id is not None,
        result=AnalysisResult.model_validate(analysis.result),
    )


@router.post("", status_code=201)
def create_analysis(
    data: AnalysisRequest,
    request: Request,
    session: SessionDep,
    user: OptionalUserDep,
    source: ReportSourceDep,
    analyzer: AnalyzerDep,
) -> AnalysisOut:
    # Antes de qualquer consulta: não gasta pontos do Warcraft Logs com quem já não pode
    # analisar.
    check_plan_limit(session, user)

    # Lista e Magos da luta saem do cache que a tela de escolher a luta já encheu. Os eventos
    # saem da pré-busca e os tops do cache de 24 h: ver `EngineAnalyzer` (services/analyzer.py).
    client = request_client(request, user)
    report, fight = load_fight(source, data.report_code, data.fight_id, client)
    # Só os Magos Arcanos da luta: id de fora dela ou de outra spec cai aqui.
    player = load_player(source, report, fight, data.actor_id, client)

    try:
        # Warcraft Logs fora do ar ou limite (eventos ou tops): mesmos códigos das outras rotas.
        result = call_source(source, lambda: analyzer.analyze(report, fight, player))
    except AnalysisNotAvailableError as exc:
        # Antes de gravar: não entra no histórico nem conta no limite do plano.
        raise api_error(
            503, "analysis_not_available", _not_available_message(exc, source)
        ) from None

    analysis = Analysis(
        user_id=user.id if user else None,
        report_code=report.code,
        fight_id=fight.id,
        player_name=player.name,
        boss=fight.boss,
        difficulty=fight.difficulty,
        dps=result.summary.dps,
        dps_gap_pct=result.summary.dps_gap_pct,
        mistakes_count=len(result.mistakes),
        result=result.model_dump(mode="json"),
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return _to_out(analysis)


@router.get("/{analysis_id}")
def read_analysis(analysis_id: str, session: SessionDep, user: OptionalUserDep) -> AnalysisOut:
    analysis = session.get(Analysis, analysis_id)
    # Análise de outra conta aparece como inexistente, para não vazar que ela existe.
    if analysis is None or (analysis.user_id and (user is None or user.id != analysis.user_id)):
        raise api_error(404, "analysis_not_found", "Não encontramos essa análise.")
    return _to_out(analysis)
