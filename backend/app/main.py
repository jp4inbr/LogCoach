import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api import analyses, auth, me, reports
from app.config import get_settings
from app.db import create_tables
from app.errors import UNEXPECTED_ERROR_CODE, UNEXPECTED_ERROR_MESSAGE, error_response
from app.services.sources import shutdown_prefetch
from app.services.tops import shutdown_tops
from app.wcl.client import close_shared_client, stop_shared_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Sem migrações no MVP: as tabelas são criadas na subida se ainda não existirem.
    create_tables()
    yield
    # As buscas de eventos param na próxima página, a fila da pré-busca é cancelada e só
    # então o cliente do WCL fecha.
    stop_shared_client()
    shutdown_prefetch()
    shutdown_tops()
    close_shared_client()


class UnexpectedErrorMiddleware:
    """Exceção não tratada vira 500 no formato de sempre (`detail.code`/`detail.message`).

    Fica dentro do CORS de propósito: um `exception_handler(Exception)` do FastAPI roda fora
    dos middlewares, a resposta sai sem os cabeçalhos de CORS e o navegador nem deixa o
    frontend ler o erro. Os `api_error` (HTTPException) já viram resposta antes de chegar
    aqui, então passam intactos.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_tracking(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_tracking)
        except Exception:
            logger.exception("Erro inesperado em %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise  # a resposta já começou: não dá para trocar por outra
            response = error_response(500, UNEXPECTED_ERROR_CODE, UNEXPECTED_ERROR_MESSAGE)
            await response(scope, receive, send)


app = FastAPI(title="LogCoach", lifespan=lifespan)

# Adicionado antes do CORS para ficar por dentro dele (o último adicionado é o de fora).
app.add_middleware(UnexpectedErrorMiddleware)
# Libera o frontend em desenvolvimento (porta padrão do Vite).
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(reports.router)
app.include_router(analyses.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
