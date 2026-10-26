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
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"


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
    # RF25 no modo exemplo: mapa pseudônimo → nome real gerado pelo save_fixtures.py.
    # Fica fora do git; sem ele, os nomes vêm nulos e o botão de mostrar fica desabilitado.
    names_file: Path = BACKEND_DIR / "tests" / "fixtures" / "names.local.json"

    @model_validator(mode="after")
    def _default_data_source(self) -> "Settings":
        has_wcl = bool(self.wcl_client_id and self.wcl_client_secret)
        if self.data_source is None:
            self.data_source = "wcl" if has_wcl else "exemplo"
        elif self.data_source == "wcl" and not has_wcl:
            # Falha na subida em vez de cada busca virar "relatório privado" para o usuário.
            raise ValueError("DATA_SOURCE=wcl exige WCL_CLIENT_ID e WCL_CLIENT_SECRET.")
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
