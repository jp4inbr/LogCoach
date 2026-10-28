---
description: Indicadores objetivos da qualidade do sistema.
---

# 11. Métricas de Qualidade

> Entrega da RT03 / banca. Preencher os valores medidos.

| Métrica                                 | Meta                   | Como medir                    | Resultado |
| --------------------------------------- | ---------------------- | ----------------------------- | --------- |
| Testes passando                         | 100%                   | `pytest` no CI                |           |
| Cobertura de testes do motor de análise | ≥ 70%                  | `pytest --cov=app/engine`     |           |
| Erros de lint                           | 0                      | `ruff check` e `eslint` no CI |           |
| Tempo de carregamento das páginas       | < 3 s (RNF01)          | DevTools do navegador         |           |
| Tempo de uma análise completa           | < 2 min (RNF02)        | Log do backend                |           |
| Tempo da 1ª análise por usuário novo    | ≤ 5 min (RNF09)        | Teste de usabilidade          |           |
| Nota SUS                                | ≥ 68                   | Questionário SUS (item 8)     |           |
| Taxa de sucesso nas tarefas do teste    | ≥ 80%                  | Teste de usabilidade          |           |
| Responsividade                          | OK de 360 px a desktop | Teste manual em celular e PC  |           |
