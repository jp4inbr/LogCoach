"""Configurações do backend, lidas das variáveis de ambiente e do arquivo backend/.env."""

import logging
import secrets
from functools import lru_cache
from pathlib import Path, PureWindowsPath
from typing import Literal

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

    Sem isso, "sqlite:///./logcoach.db" cria um banco em cada pasta de onde o
    uvicorn sobe. Memória, caminho absoluto, URI `file:` e outros bancos ficam como estão.
    """
    parsed = make_url(url)  # entende drivers (sqlite+pysqlite://) e query string
    path = parsed.database
    if (
        parsed.get_backend_name() != "sqlite"
        or not path
        or path == ":memory:"
        or parsed.query.get("uri")
        # Absoluto no Unix ("/abs/x.db") ou no Windows ("C:/x.db"); PureWindowsPath decide
        # igual em qualquer sistema, então o caso do Windows também é testado no Mac/Linux.
        or path.startswith("/")
        or PureWindowsPath(path).is_absolute()
    ):
        return url
    absolute = (BACKEND_DIR / path).resolve().as_posix()
    # O render_as_string troca o ":" de "C:/..." por "%3A". O SQLAlchemy lê de volta, mas a
    # URL fica ilegível e os testes falham no Windows; por isso o caminho entra depois.
    rendered = parsed.set(database="").render_as_string(hide_password=False)
    return rendered.replace(":///", f":///{absolute}", 1)


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
