"""Erros da API com código fixo e mensagem pronta para o usuário (item 8.2)."""

from fastapi import HTTPException
from fastapi.responses import JSONResponse

# Exceção que ninguém tratou (bug nosso): o handler de `app/main.py` responde com isto.
UNEXPECTED_ERROR_CODE = "unexpected_error"
UNEXPECTED_ERROR_MESSAGE = (
    "Erro inesperado no LogCoach. O problema é nosso, não do seu relatório. "
    "Tente de novo; se continuar, recarregue a página."
)


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    """O frontend decide o que fazer pelo `code` e mostra a `message` ao usuário."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Mesmo corpo do `api_error`, para quem responde fora das rotas (middleware)."""
    return JSONResponse(
        status_code=status_code, content={"detail": {"code": code, "message": message}}
    )
