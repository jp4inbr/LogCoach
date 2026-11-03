---
description: Código-fonte versionado no GitHub.
---

# 7. Repositório de Código Versionado

**Repositório:** [github.com/jp4inbr/LogCoach](https://github.com/jp4inbr/LogCoach)

A documentação deste GitBook fica na pasta `docs/` do repositório e é sincronizada nos dois sentidos pelo **GitBook Git Sync**.

## Estrutura

```
LogCoach/
├── docs/             # este GitBook (Git Sync)
├── backend/          # FastAPI
│   ├── app/
│   │   ├── api/      # rotas
│   │   ├── engine/   # coletor, regras, comparador
│   │   ├── rules/    # regras da especialização em YAML (ex.: arcane_mage.yaml)
│   │   ├── encounters/ # regras de cada chefe em YAML (ex.: nekzali.yaml)
│   │   └── ai/       # integração com Vertex AI
│   └── tests/        # Pytest
├── frontend/         # React + Vite
└── .github/workflows # CI: lint + testes (Ubuntu e Windows)
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
import react from "eslint-plugin-react";
import prettier from "eslint-config-prettier";

export default [
  js.configs.recommended,
  react.configs.flat.recommended,
  prettier,
];
```

```json
{ "semi": true, "singleQuote": false, "printWidth": 100 }
```

**Pre-commit** — `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: vX.Y.Z  # rodar `pre-commit autoupdate` para fixar a versão atual
    hooks:
      - id: ruff
      - id: ruff-format
```

## Princípios aplicados (Clean Code / SOLID)

* Cada regra do Mago Arcano é uma classe pequena com uma única responsabilidade (**S**).
* Regras novas entram sem alterar o motor (**O**): o motor lê a lista de regras do YAML.
* O motor depende de uma interface de "fonte de dados", então dá para trocar a API real por arquivo de teste (**D**).

## Padrões do time

* Branch por tarefa: `feat/...`, `fix/...`, `docs/...`.
* Commits curtos e no imperativo (ex.: `feat: adiciona regra de tempo parado`).
* Nada de chave de API no código: segredos só no `.env` (já no `.gitignore`).
