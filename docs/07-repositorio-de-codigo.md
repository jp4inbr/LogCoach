---
description: Código-fonte versionado no GitHub.
---

# 7. Repositório de Código Versionado

**Repositório:** [github.com/jp4inbr/LogCoach](https://github.com/jp4inbr/LogCoach)

A documentação deste GitBook fica na pasta `docs/` do repositório e é sincronizada nos dois sentidos pelo **GitBook Git Sync**.

## Estrutura

```
LogCoach/
├── docs/                 # este GitBook (Git Sync)
├── backend/              # FastAPI
│   ├── app/
│   │   ├── api/          # rotas: auth, me, reports (resolve, players, prefetch), analyses
│   │   ├── engine/       # motor: fight, timeline, measures, checks, baseline, abilities,
│   │   │                 # targets, damage, support, cooldowns, potion, uptime, defensives,
│   │   │                 # arcane_soul, prismatic_bolt, context, names, rules, report
│   │   ├── services/     # sources.py (ReportSource, Analyzer), tops.py (TopsSource),
│   │   │                 # analyzer.py (EngineAnalyzer), links.py, plan.py
│   │   ├── wcl/          # cliente do Warcraft Logs: client, queries, fetch, players,
│   │   │                 # tops, anonymize
│   │   ├── rules/        # regras do Mago Arcano em YAML (arcane_mage.yaml)
│   │   ├── encounters/   # regras de cada chefe em YAML (nekzali.yaml)
│   │   ├── guides/       # guias em português para a IA (arcane_mage.md, nekzali.md)
│   │   ├── i18n/         # nomes em português por ID (pt_br.yaml)
│   │   ├── samples/      # modo exemplo: kill de referência e tops (tops/)
│   │   ├── ai/           # integração com a IA: ainda vazio (passo 5)
│   │   └── config.py, db.py, models.py, schemas.py, security.py, errors.py, main.py
│   ├── scripts/          # save_fixtures.py: baixa o kill de referência e o top 10
│   └── tests/            # Pytest (test_engine_*, test_analyzer, test_reports, test_wcl*...)
│       └── fixtures/     # kill de referência e top 10 anonimizados
├── frontend/             # React + Vite
│   └── src/
│       ├── pages/        # Home, Login, ChooseFight, Result, Profile, Plans
│       ├── components/   # Timeline, MistakeCard, GapBreakdown, TargetsTable, ComparedPlayers...
│       └── lib/          # api.js, router.js, auth-context.js, format.js...
└── .github/workflows     # CI: lint + testes (Ubuntu e Windows)
```

## Linters e formatadores

**Python** — `backend/pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N"]

[tool.ruff.format]
quote-style = "double"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**JavaScript** — `frontend/eslint.config.js` + `frontend/.prettierrc`:

```js
import js from "@eslint/js";
import globals from "globals";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import prettier from "eslint-config-prettier";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  globalIgnores(["dist"]),
  {
    files: ["**/*.{js,jsx}"],
    extends: [
      js.configs.recommended,
      react.configs.flat.recommended,
      react.configs.flat["jsx-runtime"],
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      prettier,
    ],
    settings: { react: { version: "detect" } },
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      // Sem TypeScript nem prop-types no projeto: as props ficam documentadas no próprio componente.
      "react/prop-types": "off",
    },
  },
]);
```

```json
{ "semi": true, "singleQuote": false, "printWidth": 100 }
```

**Pre-commit** — `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.17.1  # rodar `pre-commit autoupdate` para fixar a versão atual
    hooks:
      - id: ruff
      - id: ruff-format
```

## Princípios aplicados (Clean Code / SOLID)

* **S:** cada módulo do motor cuida de uma coisa só: `cooldowns.py` (Surge e Touch), `potion.py` (poção), `defensives.py` (picos de dano), `prismatic_bolt.py` (decisão × sorte), `report.py` (montar o resultado) etc. O cliente do Warcraft Logs (`wcl/`) não sabe de cache nem de regras; o motor não sabe de Warcraft Logs nem de rotas.
* **O:** mecânicas do jogo, limites reserva e regras do chefe ficam em YAML (`rules/arcane_mage.yaml`, `encounters/nekzali.yaml`). Ajustar um valor a cada patch ou descrever outro chefe não exige mudar o motor (RNF12).
* **D:** as rotas dependem de interfaces, não das implementações: `ReportSource` e `Analyzer` (`services/sources.py`) e `TopsSource` (`services/tops.py`). A `DATA_SOURCE` escolhe entre a API real (`WclReportSource`, `WclTopsSource`) e os arquivos de `app/samples/` (`SampleReportSource`, `SampleTopsSource`), sem internet. O analisador é o `EngineAnalyzer` (`services/analyzer.py`).

## Padrões do time

* **Branch por frente**, com nome `tipo/assunto` (ex.: `feat/motor-base`, `feat/pendencias-wcl`, `chore/simplificacoes-wcl`).
* **Pull request antes da `main`**, com o CI verde: lint e testes do backend (Ruff, Pytest) e do frontend (ESLint, build do Vite), em Ubuntu e Windows.
* **Commits em português** no padrão `tipo(escopo): descrição`, com `feat`, `fix`, `docs`, `chore` ou `test` (ex.: `feat(api): EngineAnalyzer na rota de análises`, `fix(motor): combo Surge→Touch aponta o Touch mais próximo`).
* Nada de chave de API no código: segredos só no `backend/.env` (já no `.gitignore`; modelo em `.env.example`). As fixtures do repositório usam pseudônimos no lugar dos nomes dos jogadores.
