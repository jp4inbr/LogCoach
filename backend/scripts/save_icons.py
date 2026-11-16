"""Baixa os ícones das magias do Mago Arcano e escreve o catálogo do frontend.

Uso (de dentro de backend/):
    python scripts/save_icons.py            # fixtures, WCL para o que faltar, download
    python scripts/save_icons.py --offline  # só fixtures e arquivos já baixados (sem rede)
    python scripts/save_icons.py --force    # baixa de novo as imagens que já existem

Saída:
    frontend/public/icons/<arquivo>          a imagem de cada ícone
    frontend/src/data/spell-icons.json       {"365350": "spell_arcane_xxx.jpg", ...}

A lista de IDs é a `mage_spells` do `app/i18n/pt_br.yaml` (a mesma da marcação dos textos,
item 12.9). O nome do ícone vem do `masterData.abilities[].icon` das fixtures; o que faltar
vem do `gameData { ability(id) { icon } }` do Warcraft Logs (poucos pontos).

Os ícones são arte da Blizzard Entertainment, usados só com fim acadêmico (A3 de Usabilidade).
"""

import argparse
import glob
import gzip
import json
import re
import sys
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.engine.names import mage_spell_ids  # noqa: E402

ICONS_DIR = ROOT / "frontend" / "public" / "icons"
CATALOG = ROOT / "frontend" / "src" / "data" / "spell-icons.json"
FIGHT_FILES = [
    *glob.glob(str(BACKEND / "tests" / "fixtures" / "**" / "*.json.gz"), recursive=True),
    *glob.glob(str(BACKEND / "app" / "samples" / "*.json.gz")),
]
SOURCES = (
    "https://assets.rpglogs.com/img/warcraft/abilities/{icon}",
    "https://wow.zamimg.com/images/wow/icons/large/{stem}.jpg",
)


ICON_NAME_RE = re.compile(r"[\w.-]+\.(jpg|png)")
MAGIC = {".jpg": b"\xff\xd8\xff", ".png": b"\x89PNG\r\n\x1a\n"}


def valid_icon_name(icon: object) -> bool:
    """Só nome simples de arquivo de imagem (a API é externa: nada de caminho)."""
    return isinstance(icon, str) and ICON_NAME_RE.fullmatch(icon) is not None


def is_image(icon: str, content: bytes) -> bool:
    """Os primeiros bytes batem com a extensão (uma página de erro com status 200 não passa)."""
    return content.startswith(MAGIC[Path(icon).suffix])


def icons_from_fixtures(ids: set[int]) -> dict[int, str]:
    found: dict[int, str] = {}
    for path in FIGHT_FILES:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        for ability in data.get("abilities") or []:
            if ability.get("gameID") in ids and valid_icon_name(ability.get("icon")):
                found.setdefault(ability["gameID"], ability["icon"])
    return found


def icons_from_wcl(ids: list[int]) -> dict[int, str]:
    from app.wcl.client import WclClient

    found: dict[int, str] = {}
    with WclClient.from_env() as client:
        for ability_id in ids:
            data = client.query(f"{{ gameData {{ ability(id: {ability_id}) {{ id icon }} }} }}")
            ability = (data.get("gameData") or {}).get("ability") or {}
            if valid_icon_name(ability.get("icon")):
                found[ability_id] = ability["icon"]
    return found


def has_image(icon: str) -> bool:
    target = ICONS_DIR / icon
    return target.is_file() and is_image(icon, target.read_bytes()[:8])


def download(icon: str, force: bool) -> bool:
    target = ICONS_DIR / icon
    if not force and has_image(icon):
        return True
    for template in SOURCES:
        url = template.format(icon=icon, stem=Path(icon).stem)
        try:
            response = httpx.get(url, timeout=20, follow_redirects=True)
        except httpx.HTTPError:
            continue
        if response.status_code == 200 and is_image(icon, response.content):
            ICONS_DIR.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--offline", action="store_true", help="não consulta a rede")
    parser.add_argument("--force", action="store_true", help="baixa de novo as imagens")
    args = parser.parse_args()

    ids = set(mage_spell_ids())
    icons = icons_from_fixtures(ids)
    if CATALOG.exists():  # o que já estava no catálogo vale (ex.: ID que só o WCL online conhece)
        for key, icon in json.loads(CATALOG.read_text(encoding="utf-8")).items():
            if int(key) in ids and valid_icon_name(icon):
                icons.setdefault(int(key), icon)
    missing = sorted(ids - icons.keys())
    if missing and not args.offline:
        print(
            f"Sem ícone nas fixtures nem no catálogo ({len(missing)}): consultando o WCL: {missing}"
        )
        icons.update(icons_from_wcl(missing))

    no_icon = sorted(ids - icons.keys())
    no_file = []
    for ability_id, icon in sorted(icons.items()):
        if args.offline:
            ok = has_image(icon)
        else:
            ok = download(icon, args.force)
        if not ok:
            no_file.append(ability_id)
    catalog = {str(i): icon for i, icon in sorted(icons.items()) if i not in no_file}
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(catalog)} de {len(ids)} IDs no catálogo ({CATALOG}).")
    if no_icon:
        print(f"Sem nome de ícone: {no_icon}")
    if no_file:
        print(f"Imagem não baixada: {no_file}")
    if no_icon or no_file:
        sys.exit(1)  # catálogo incompleto: quem roda (ou o CI) tem de notar


if __name__ == "__main__":
    main()
