"""Cadastro e login (RF02)."""

from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import SessionDep
from app.errors import api_error
from app.models import User
from app.schemas import Credentials, LoginData, Token
from app.security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["contas"])


@router.post("/register", status_code=201)
def register(data: Credentials, session: SessionDep) -> Token:
    email = data.email.lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise api_error(409, "email_taken", "Já existe uma conta com esse e-mail. Tente entrar.")
    user = User(email=email, password_hash=hash_password(data.password))
    session.add(user)
    session.commit()
    return Token(access_token=create_token(user.id))


@router.post("/login")
def login(data: LoginData, session: SessionDep) -> Token:
    user = session.exec(select(User).where(User.email == data.email.lower())).first()
    # Mesma mensagem para e-mail inexistente e senha errada: não revela quem tem conta.
    if user is None or not verify_password(data.password, user.password_hash):
        raise api_error(401, "invalid_credentials", "E-mail ou senha incorretos.")
    return Token(access_token=create_token(user.id))
