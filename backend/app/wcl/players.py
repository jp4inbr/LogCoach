"""Acha o jogador entre os atores de um report do WCL (masterData.actors).

O jogador analisado vem pelo id do ator (o `/reports/resolve` já entrega o id). Os top 10
vêm do ranking só com nome + reino, então a busca por nome também existe, mas só aqui.
"""

from typing import Any

from app.wcl.client import WclError


class PlayerNotFoundError(WclError):
    """Nenhum jogador com esse id (ou nome + reino) no report, ou nome ambíguo."""


def normalize_server(server: str | None) -> str:
    """ "Area 52", "area-52" e "Area52" são o mesmo reino."""
    return (server or "").replace(" ", "").replace("-", "").lower()


def find_player(
    actors: list[dict[str, Any]],
    *,
    actor_id: int | None = None,
    name: str | None = None,
    server: str | None = None,
) -> dict[str, Any]:
    """Pelo id do ator ou por nome + reino (um dos dois)."""
    if (actor_id is None) == (name is None):
        raise ValueError("Informe actor_id ou name, não os dois.")
    players = [a for a in actors if a["type"] == "Player"]

    if actor_id is not None:
        found = next((a for a in players if a["id"] == actor_id), None)
        if found is None:
            raise PlayerNotFoundError(f"Jogador de id {actor_id} não está no report.")
        return found

    same_name = [a for a in players if a["name"] == name]
    if server:
        same_server = [
            a for a in same_name if normalize_server(a.get("server")) == normalize_server(server)
        ]
        # Ator sem reino (ex.: fixture anonimizada) e nome único: vale só o nome.
        if not same_server and len(same_name) == 1 and not same_name[0].get("server"):
            same_server = same_name
        same_name = same_server
    if not same_name:
        raise PlayerNotFoundError(f"Jogador {name!r} ({server or 'sem reino'}) não está no report.")
    if len(same_name) > 1:
        raise PlayerNotFoundError(f"Há mais de um {name!r} no report; informe o reino.")
    return same_name[0]
