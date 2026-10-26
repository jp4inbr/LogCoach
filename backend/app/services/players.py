"""Acha o jogador pedido entre os Magos Arcanos da luta (nome + reino)."""

from app.schemas import PlayerOption


class PlayerNotFoundError(Exception):
    """Nenhum Mago Arcano com esse nome (e reino) na luta."""


class AmbiguousPlayerError(Exception):
    """Mais de um Mago Arcano com esse nome, e o reino não desempatou."""


def normalize_server(server: str | None) -> str:
    """Mesma regra de `wcl/fetch.py`: "Area 52", "area-52" e "Area52" são o mesmo reino."""
    return (server or "").replace(" ", "").replace("-", "").lower()


def match_player(players: list[PlayerOption], name: str, server: str | None) -> PlayerOption:
    same_name = [p for p in players if p.name == name]
    if not same_name:
        raise PlayerNotFoundError(name)

    if len(same_name) == 1:
        player = same_name[0]
        # Reino pedido e diferente do conhecido: é outro personagem, melhor não analisar.
        # Sem reino de um dos lados (ex.: exemplo), vale só o nome.
        if server and player.server and normalize_server(server) != normalize_server(player.server):
            raise PlayerNotFoundError(name)
        return player

    if server:
        same_name = [p for p in same_name if normalize_server(p.server) == normalize_server(server)]
    if len(same_name) != 1:
        raise AmbiguousPlayerError(name)
    return same_name[0]
