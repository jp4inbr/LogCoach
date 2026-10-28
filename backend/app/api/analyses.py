"""Rodar uma análise e abrir o resultado (RF01, RF10, RF12, RF14)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import OptionalUserDep, SessionDep
from app.api.reports import ReportSourceDep, load_fight, load_player
from app.config import get_settings
from app.errors import api_error
from app.models import Analysis
from app.schemas import AnalysisOut, AnalysisRequest, AnalysisResult
from app.services.plan import analyses_this_month
from app.services.sources import AnalysisNotAvailableError, Analyzer, get_analyzer

router = APIRouter(prefix="/analyses", tags=["análises"])

AnalyzerDep = Annotated[Analyzer, Depends(get_analyzer)]


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
    session: SessionDep,
    user: OptionalUserDep,
    source: ReportSourceDep,
    analyzer: AnalyzerDep,
) -> AnalysisOut:
    # Lista e Magos da luta saem do cache que a tela de escolher a luta já encheu. Os eventos
    # (quando o motor entrar) saem da pré-busca: ver `Analyzer` em services/sources.py.
    report, fight = load_fight(source, data.report_code, data.fight_id)
    # Só os Magos Arcanos da luta: id de fora dela ou de outra spec cai aqui.
    player = load_player(source, report, fight, data.actor_id)

    limit = get_settings().free_monthly_limit
    if user is not None and analyses_this_month(session, user.id) >= limit:
        raise api_error(
            403,
            "plan_limit",
            f"Você usou suas {limit} análises do mês. Veja o plano Pro.",
        )

    try:
        result = analyzer.analyze(report, fight, player)
    except AnalysisNotAvailableError:
        raise api_error(
            503,
            "analysis_not_available",
            "Ainda não conseguimos analisar essa luta com esse personagem. Nesta versão alfa, "
            "só há análise do Harmonist no Nek'zali Mítico (luta 34 do log de exemplo).",
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
