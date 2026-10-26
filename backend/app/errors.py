"""Erros da API com código fixo e mensagem pronta para o usuário (item 8.2)."""

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    """O frontend decide o que fazer pelo `code` e mostra a `message` ao usuário."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
