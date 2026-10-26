"""Configurações do backend, lidas das variáveis de ambiente e do arquivo backend/.env."""

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Caminho absoluto: o .env é lido igual, não importa de que pasta o uvicorn sobe.
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    # env_ignore_empty: "DATA_SOURCE=" no .env vale como não definida.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore", env_ignore_empty=True)

    app_env: Literal["dev", "prod"] = "dev"
    database_url: str = "sqlite:///./logcoach.db"
    jwt_secret: str = ""
    jwt_expire_days: int = 7
    # RF14: limite de análises por mês no plano grátis.
    free_monthly_limit: int = 5
    cors_origins: list[str] = ["http://localhost:5173"]

    wcl_client_id: str = ""
    wcl_client_secret: str = ""
    # De onde vêm os relatórios: "wcl" (API real) ou "exemplo" (app/samples, sem internet).
    # Sem valor: "wcl" quando há as duas credenciais do Warcraft Logs, senão "exemplo".
    data_source: Literal["wcl", "exemplo"] | None = None

    @model_validator(mode="after")
    def _default_data_source(self) -> "Settings":
        if self.data_source is None:
            has_wcl = bool(self.wcl_client_id and self.wcl_client_secret)
            self.data_source = "wcl" if has_wcl else "exemplo"
        return self


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.jwt_secret:
        if settings.app_env == "prod":
            raise RuntimeError(
                "JWT_SECRET não definido. Em produção (APP_ENV=prod) ele é obrigatório: "
                "sem ele os logins não sobrevivem a um reinício."
            )
        # Sem JWT_SECRET o backend ainda sobe em desenvolvimento, mas os logins
        # deixam de valer a cada reinício.
        logger.warning("JWT_SECRET vazio: usando uma chave temporária só para esta execução.")
        settings.jwt_secret = secrets.token_urlsafe(32)
    return settings
