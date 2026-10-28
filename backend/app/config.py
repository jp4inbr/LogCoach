"""Configurações do backend, lidas das variáveis de ambiente e do arquivo backend/.env."""

import logging
import secrets
from functools import lru_cache
from pathlib import Path, PureWindowsPath
from typing import Literal
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)

# Caminho absoluto: o .env é lido igual, não importa de que pasta o uvicorn sobe.
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"
DEFAULT_DB = BACKEND_DIR / "logcoach.db"
SQLITE_FILE = "sqlite:///"


def resolve_sqlite_url(url: str) -> str:
    """Resolve a partir de backend/ o caminho relativo de uma URL SQLite.

    Garante que URLs relativas do SQLite sejam resolvidas corretamente
    a partir da pasta backend/ do projeto, evitando que o banco seja
    criado em pastas diferentes dependendo de onde o uvicorn é executado.
    """
    parsed = make_url(url)
    path = parsed.database

    # Verifica se a URL NÃO deve ser alterada:
    # 1. Se não for SQLite (ex: PostgreSQL)
    # 2. Se não houver caminho definido
    # 3. Se for banco em memória (:memory:)
    # 4. Se contiver query string de URI especial
    # 5. Se já for um caminho absoluto no Unix ou Windows
    if (
        parsed.get_backend_name() != "sqlite"
        or not path
        or path == ":memory:"
        or parsed.query.get("uri")
        or path.startswith("/")
        or PureWindowsPath(path).is_absolute()
    ):
        return url

    # Se for relativo, resolve o caminho absoluto combinando com 'backend/'
    absolute = (BACKEND_DIR / path).resolve()

    # Extrai o driver e preserva eventuais parâmetros de query string
    driver = url.split("://")[0]
    parsed_full = urlparse(url)
    query_part = f"?{parsed_full.query}" if parsed_full.query else ""

    return f"{driver}:///{absolute.as_posix()}{query_part}"


class Settings(BaseSettings):
    # env_ignore_empty: "DATA_SOURCE=" no .env vale como não definida.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore", env_ignore_empty=True)

    app_env: Literal["dev", "prod"] = "dev"
    # Vazio = backend/logcoach.db; caminho relativo vale a partir de backend/.
    database_url: str = f"{SQLITE_FILE}{DEFAULT_DB.as_posix()}"
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

    @field_validator("database_url")
    @classmethod
    def _absolute_sqlite(cls, url: str) -> str:
        return resolve_sqlite_url(url)

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
