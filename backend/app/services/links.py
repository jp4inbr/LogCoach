"""Validação do link do Warcraft Logs (RF03)."""

import re

# Com ou sem https e com qualquer subdomínio (quem decide se ele vale é `parse_report_code`);
# ignora o que vem depois do código (#fight=34, ?type=damage-done...).
_REPORT_LINK = re.compile(
    r"^(?:https?://)?(?:(?P<sub>[a-z]+)\.)?warcraftlogs\.com/reports/"
    r"(?P<code>[A-Za-z0-9]{6,40})(?:[/?#].*)?$"
)
# Só o World of Warcraft atual: www., sem subdomínio ou um de idioma de 2 letras (de., fr.,
# ko., cn., br.: o site traduzido, com o mesmo código de relatório).
RETAIL_SUBDOMAINS = {None, "www"}
# Warcraft Logs Classic (Cataclysm/MoP Classic, Season of Discovery, Fresh, Vanilla/Era): o
# link tem o mesmo formato, mas o log é de outro jogo e a API é outra.
CLASSIC_SUBDOMAINS = {"classic", "sod", "fresh", "vanilla", "era"}


def _match(url: str) -> re.Match[str] | None:
    return _REPORT_LINK.match(url.strip())


def _is_retail(sub: str | None) -> bool:
    return sub in RETAIL_SUBDOMAINS or (len(sub) == 2 and sub not in CLASSIC_SUBDOMAINS)


def parse_report_code(url: str) -> str | None:
    """Devolve o código do relatório, ou None se o link não for do Warcraft Logs do WoW atual."""
    match = _match(url)
    if match is None or not _is_retail(match.group("sub")):
        return None
    return match.group("code")


def is_classic_link(url: str) -> bool:
    """Link de relatório do Warcraft Logs Classic (a rota explica que só o WoW atual vale)."""
    match = _match(url)
    return match is not None and match.group("sub") in CLASSIC_SUBDOMAINS
