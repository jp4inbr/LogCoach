"""Salva em JSON o kill de referência e os top 10 do mesmo bracket de item level.

Uso (de dentro de backend/):
    python scripts/save_fixtures.py            # referência + top 10
    python scripts/save_fixtures.py --only-reference
    python scripts/save_fixtures.py --force    # sobrescreve arquivos existentes

Os arquivos versionados têm os nomes trocados por pseudônimos. O mapa com os nomes
reais vai para tests/fixtures/names.local.json, que está no .gitignore.
"""

import argparse
import gzip
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.wcl.anonymize import anonymize_fight, anonymize_ranking  # noqa: E402
from app.wcl.client import WclClient  # noqa: E402
from app.wcl.fetch import (  # noqa: E402
    bracket_index,
    bracket_range,
    fetch_brackets,
    fetch_fight,
    fetch_rankings,
)

# Kill de referência (ver CLAUDE.md).
REFERENCE = {"report": "XhrmBaYkGCAQjH2D", "fight": 34, "player": "Harmonist"}
ENCOUNTER_ID = 3470
CLASS_NAME, SPEC_NAME = "Mage", "Arcane"
TOP_N = 10

FIXTURES = BACKEND / "tests" / "fixtures"
NAMES_FILE = FIXTURES / "names.local.json"
RULES_FILE = BACKEND / "app" / "rules" / "arcane_mage.yaml"


def write_json(path: Path, data: Any, force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"{path} já existe. Use --force para sobrescrever.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        # Lutas: JSON compacto + gzip (cada uma tem milhares de eventos).
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        path.write_bytes(gzip.compress(raw, mtime=0))
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def summarize(label: str, fight: dict[str, Any], expected_ids: dict[str, int]) -> None:
    meta = fight["meta"]["fight"]
    duration_s = fight["meta"]["duration_ms"] / 1000
    counts = {kind: len(events) for kind, events in fight["events"].items()}
    seen = {e["abilityGameID"] for kind in ("casts", "buffs") for e in fight["events"][kind]}
    missing = [name for name, ability_id in expected_ids.items() if ability_id not in seen]
    details = fight["player"]["details"] or {}
    print(
        f"  {label}: luta {meta['id']}, {int(duration_s // 60)}:{int(duration_s % 60):02d}, "
        f"kill={meta['kill']}, fases={len(meta['phaseTransitions'] or [])}, "
        f"ilvl={details.get('maxItemLevel')}"
    )
    print(f"    eventos: {counts}")
    if missing:
        print(f"    ATENÇÃO: não apareceram no log: {', '.join(missing)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only-reference", action="store_true")
    args = parser.parse_args()

    rules = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    expected_ids = {**rules["abilities"], **rules["buffs"]}
    # Nem todo Arcano usa Time Warp ou Shimmer na luta; não vale alerta.
    for optional in ("time_warp", "shimmer", "arcane_orb"):
        expected_ids.pop(optional, None)

    names: dict[str, Any] = {}
    with WclClient.from_env() as client:
        print(f"Baixando referência {REFERENCE['report']} luta {REFERENCE['fight']}…")
        ref = fetch_fight(client, REFERENCE["report"], REFERENCE["fight"], REFERENCE["player"])
        ilvl = ref["player"]["details"]["maxItemLevel"]
        brackets = fetch_brackets(client, ENCOUNTER_ID)
        index = bracket_index(ilvl, brackets["min"], brackets["bucket"])
        low, high = bracket_range(index, brackets["min"], brackets["bucket"])
        out_dir = FIXTURES / f"nekzali_mythic_{low}_{high}"

        ref_anon, ref_names = anonymize_fight(
            ref, "reference", keep=frozenset({REFERENCE["player"]}), hide_report=False
        )
        names["reference_harmonist.json.gz"] = ref_names
        write_json(out_dir / "reference_harmonist.json.gz", ref_anon, args.force)
        summarize("referência", ref, expected_ids)

        index_data: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "encounter_id": ENCOUNTER_ID,
            "difficulty": 5,
            "spec": f"{SPEC_NAME} {CLASS_NAME}",
            "bracket": {"index": index, "min_item_level": low, "max_item_level": high},
            "reference": {"file": "reference_harmonist.json.gz", **REFERENCE},
            "top": [],
        }

        if not args.only_reference:
            print(f"Buscando top {TOP_N} do bracket {low}–{high} (índice {index})…")
            rankings = fetch_rankings(
                client, ENCOUNTER_ID, CLASS_NAME, SPEC_NAME, bracket=index, n=TOP_N
            )
            ref_key = (REFERENCE["report"], REFERENCE["fight"])
            if any((r["report"]["code"], r["report"]["fightID"]) == ref_key for r in rankings):
                # RF21: quem já está no top 10 do bracket é comparado com o 1º geral.
                print("  O jogador de referência já está no top 10 do bracket (RF21).")
                index_data["reference_in_top"] = True

            for rank, ranking in enumerate(rankings, start=1):
                label = f"top{rank:02d}"
                server = (ranking.get("server") or {}).get("name")
                fight = fetch_fight(
                    client,
                    ranking["report"]["code"],
                    ranking["report"]["fightID"],
                    ranking["name"],
                    server,
                )
                fight_anon, fight_names = anonymize_fight(fight, label)
                public, real = anonymize_ranking(ranking, label)
                fight_anon["ranking"] = {"rank": rank, **public}
                names[f"{label}.json.gz"] = {**fight_names, "ranking": real}
                write_json(out_dir / f"{label}.json.gz", fight_anon, args.force)
                index_data["top"].append({"file": f"{label}.json.gz", "rank": rank, **public})
                summarize(label, fight, expected_ids)

        write_json(out_dir / "index.json", index_data, force=True)
        names_all = (
            json.loads(NAMES_FILE.read_text(encoding="utf-8")) if NAMES_FILE.exists() else {}
        )
        names_all[out_dir.name] = names
        NAMES_FILE.write_text(json.dumps(names_all, ensure_ascii=False, indent=1), encoding="utf-8")

        rate = client.query("{ rateLimitData { limitPerHour pointsSpentThisHour } }")
        print(f"Pontos da API nesta hora: {rate['rateLimitData']}")
    print(f"Fixtures em {out_dir.relative_to(BACKEND)}")


if __name__ == "__main__":
    main()
