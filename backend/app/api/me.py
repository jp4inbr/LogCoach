"""Conta do usuário logado: dados, histórico, troca de senha e exclusão (RF12, RNF07)."""

from fastapi import APIRouter, Response
from sqlalchemy import delete
from sqlmodel import col, select

from app.api.deps import CurrentUserDep, SessionDep
from app.config import get_settings
from app.errors import api_error
from app.models import Analysis
from app.schemas import AnalysisSummary, Me, PasswordChange
from app.security import hash_password, verify_password
from app.services.plan import analyses_this_month

router = APIRouter(prefix="/me", tags=["contas"])


@router.get("")
def read_me(user: CurrentUserDep, session: SessionDep) -> Me:
    return Me(
        email=user.email,
        created_at=user.created_at,
        analyses_this_month=analyses_this_month(session, user.id),
        monthly_limit=get_settings().free_monthly_limit,
    )


@router.get("/analyses")
def list_my_analyses(user: CurrentUserDep, session: SessionDep) -> list[AnalysisSummary]:
    """Histórico do usuário, da mais recente para a mais antiga."""
    query = (
        select(Analysis)
        .where(Analysis.user_id == user.id)
        .order_by(col(Analysis.created_at).desc())
    )
    return [AnalysisSummary.model_validate(a, from_attributes=True) for a in session.exec(query)]


@router.put("/password", status_code=204)
def change_password(data: PasswordChange, user: CurrentUserDep, session: SessionDep) -> Response:
    if not verify_password(data.current_password, user.password_hash):
        raise api_error(400, "wrong_password", "A senha atual não confere.")
    user.password_hash = hash_password(data.new_password)
    session.add(user)
    session.commit()
    return Response(status_code=204)


@router.delete("", status_code=204)
def delete_me(user: CurrentUserDep, session: SessionDep) -> Response:
    """Apaga a conta e todas as análises dela (RNF07, LGPD)."""
    session.execute(delete(Analysis).where(col(Analysis.user_id) == user.id))
    session.delete(user)
    session.commit()
    return Response(status_code=204)
