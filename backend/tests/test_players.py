import pytest

from app.schemas import PlayerOption
from app.services.players import (
    AmbiguousPlayerError,
    PlayerNotFoundError,
    match_player,
    normalize_server,
)


def mage(name: str, server: str | None) -> PlayerOption:
    return PlayerOption(name=name, server=server, spec="Mago Arcano", item_level=327)


PLAYERS = [
    mage("Harmonist", "Azralon"),
    mage("Sombra", "Area 52"),
    mage("Sombra", "Tichondrius"),
]


def test_unique_name_is_found_with_or_without_server():
    assert match_player(PLAYERS, "Harmonist", None) is PLAYERS[0]
    assert match_player(PLAYERS, "Harmonist", "azralon") is PLAYERS[0]


def test_unique_name_on_another_server_is_not_found():
    with pytest.raises(PlayerNotFoundError):
        match_player(PLAYERS, "Harmonist", "Tichondrius")


def test_unique_name_without_known_server_accepts_any_server():
    # Exemplo e fixtures não têm reino: vale só o nome.
    assert match_player([mage("Harmonist", None)], "Harmonist", "Azralon").name == "Harmonist"


def test_unknown_name():
    with pytest.raises(PlayerNotFoundError):
        match_player(PLAYERS, "Ninguem", None)


def test_repeated_name_without_server_is_ambiguous():
    with pytest.raises(AmbiguousPlayerError):
        match_player(PLAYERS, "Sombra", None)


def test_repeated_name_with_unknown_server_is_ambiguous():
    with pytest.raises(AmbiguousPlayerError):
        match_player(PLAYERS, "Sombra", "Azralon")


@pytest.mark.parametrize("server", ["Area 52", "area-52", "AREA52", "Area-52"])
def test_repeated_name_is_resolved_by_server(server):
    assert match_player(PLAYERS, "Sombra", server) is PLAYERS[1]


def test_normalize_server():
    assert normalize_server("Area 52") == normalize_server("area-52") == "area52"
    assert normalize_server(None) == ""
