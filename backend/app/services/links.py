"""Validação do link do Warcraft Logs (RF03)."""

import re

# Aceita www., classic. e os outros subdomínios do site, com ou sem https,
# e ignora o que vem depois do código (#fight=34, ?type=damage-done...).
_REPORT_LINK = re.compile(
    r"^(?:https?://)?(?:[a-z]+\.)?warcraftlogs\.com/reports/(?P<code>[A-Za-z0-9]{6,40})(?:[/?#].*)?$"
)


def parse_report_code(url: str) -> str | None:
    """Devolve o código do relatório, ou None se o link não for do Warcraft Logs."""
    match = _REPORT_LINK.match(url.strip())
    return match.group("code") if match else None
