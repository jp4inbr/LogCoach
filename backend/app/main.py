from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyses, auth, me, reports
from app.config import get_settings
from app.db import create_tables


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Sem migrações no MVP: as tabelas são criadas na subida se ainda não existirem.
    create_tables()
    yield


app = FastAPI(title="LogCoach", lifespan=lifespan)

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
