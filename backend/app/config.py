"""Configurações do backend, lidas das variáveis de ambiente e do arquivo .env."""

import logging
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./logcoach.db"
    jwt_secret: str = ""
    jwt_expire_days: int = 7
    # RF14: limite de análises por mês no plano grátis.
    free_monthly_limit: int = 5
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.jwt_secret:
        # Sem JWT_SECRET o backend ainda sobe em desenvolvimento, mas os logins
        # deixam de valer a cada reinício. Em produção a variável é obrigatória.
        logger.warning("JWT_SECRET vazio: usando uma chave temporária só para esta execução.")
        settings.jwt_secret = secrets.token_urlsafe(32)
    return settings
