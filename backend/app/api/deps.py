"""Dependências comuns das rotas: sessão do banco e usuário logado."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.db import get_session
from app.errors import api_error
from app.models import User
from app.security import read_token

SessionDep = Annotated[Session, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def _user_from_token(session: Session, credentials: HTTPAuthorizationCredentials) -> User | None:
    """Dono do token, ou None se ele é inválido, venceu ou a conta foi apagada."""
    user_id = read_token(credentials.credentials)
    return session.get(User, user_id) if user_id else None


def get_optional_user(session: SessionDep, credentials: BearerDep) -> User | None:
    """Usuário do token, ou None sem login (RF01).

    Token inválido ou vencido também vale como sem login: numa rota pública ele não
    pode bloquear a análise sem conta.
    """
    if credentials is None:
        return None
    return _user_from_token(session, credentials)


def get_current_user(session: SessionDep, credentials: BearerDep) -> User:
    if credentials is None:
        raise api_error(401, "login_required", "Entre na sua conta para continuar.")
    user = _user_from_token(session, credentials)
    if user is None:
        raise api_error(401, "invalid_token", "Sua sessão expirou. Entre de novo.")
    return user


OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
