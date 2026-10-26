"""Hash de senha (argon2, RNF05) e token de login (JWT)."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.config import get_settings

_hasher = PasswordHasher()
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(user_id: str) -> str:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(days=settings.jwt_expire_days)
    return jwt.encode({"sub": user_id, "exp": expires}, settings.jwt_secret, algorithm=_ALGORITHM)


def read_token(token: str) -> str | None:
    """Devolve o id do usuário, ou None se o token for inválido ou estiver vencido."""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
