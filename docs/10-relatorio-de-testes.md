---
description: Testes unitários, de integração e de usabilidade realizados.
---

# 10. Relatório de Testes

> Entrega da RT03. Resultados de 04/11/2026, com o motor de análise na `main` (PR #27). Falta só o T07, que depende da IA (passo 5).

## 10.1 Ferramenta

**Pytest** (backend em Python). Todos os testes usam dados salvos em arquivo, sem depender da internet.

Como rodar:

```bash
cd backend
pytest -q   # ou pytest -v para ver cada teste
```

## 10.2 Casos de teste

| ID  | O que testa                             | Entrada                                            | Esperado                                          | Resultado                           |
| --- | --------------------------------------- | -------------------------------------------------- | ------------------------------------------------- | ----------------------------------- |
| T01 | Validador de link aceita link válido    | `https://www.warcraftlogs.com/reports/AbC123`      | Aceito                                            | Passou                              |
| T02 | Validador recusa link de outro site     | `https://google.com`                               | Erro de formato                                   | Passou                              |
| T03 | Regra de tempo parado                   | Luta de exemplo com 8% de tempo parado             | Status "erro"                                     | Passou (`test_engine_rules.py`, `test_t03_*`) |
| T04 | Regra de uso de cooldowns               | Luta com cooldown usado menos vezes que o possível | Status "atenção"                                  | Passou (`test_engine_rules.py`, `test_t04_cooldown_used_less_than_possible`) |
| T05 | Comparador                              | Jogador vs. média dos top logs de exemplo          | Diferença calculada corretamente                  | Passou (`test_engine_base.py`, `test_t05_top_value_is_the_mean_of_the_tops`) |
| T06 | Ordenação dos erros                     | 5 erros com impactos diferentes                    | Ordenados do maior para o menor impacto           | Passou (motor, `test_e2e_t06_mistakes_come_sorted_by_impact`) |
| T07 | Falha da IA                             | IA simulando erro                                  | Relatório só com as regras                        | Pendente (a IA entra no passo 5)    |
| T08 | Limite do plano grátis                  | 6ª análise no mês                                  | Bloqueada                                         | Passou                              |
| T09 | Luta curta                              | Luta de 40 s                                       | Mensagem de luta curta                            | Passou                              |
| T10 | Sem Mago Arcano                         | Luta sem a especialização                          | Mensagem adequada                                 | Passou (jogador fora da luta)       |
| T11 | CD dentro da janela do encontro         | CD usado 3 s após o início da janela de burst      | Marcado como alinhado                             | Passou (`test_engine_rules.py`, `test_t11_surge_held_for_the_boss_phase_is_aligned`) |
| T12 | Intermissão não conta como tempo parado | Luta com 20 s de intermissão sem casts             | Tempo parado não inclui a intermissão             | Passou (`test_engine_rules.py`, `test_t12_intermission_without_targets_is_not_idle_time`) |
| T13 | Defensivo no pico de dano               | Pico de 70% da vida em 2 s, vida a 30%, defensivo pronto e não usado | Status "atenção"                | Passou (`test_engine_peaks.py`, `test_t13_big_raid_hit_without_defensive_is_attention`) |
| T14 | Comparação por fase                     | Lutas de durações diferentes                       | Mesma janela comparada pelo tempo relativo à fase | Passou (`test_engine_base.py`, `test_t14_phases_of_different_lengths_compare_by_rate`) |

Além da tabela, o backend tem testes de contas: cadastro (e-mail repetido, senha curta, e-mail inválido), senha guardada só como hash argon2, login certo e errado, rota protegida sem token, troca de senha, análise de outra conta escondida e exclusão da conta apagando o histórico. Ficam em `backend/tests/test_auth.py`, `test_reports.py` e `test_analyses.py`.

T03–T05 e T11–T14 passam com o motor de análise. O T13 mudou junto com a decisão de 03/11: em vez de procurar o golpe de raide sem defensivo, o motor acha os **picos de dano** no log (60% da vida em 4 s ou vida abaixo de 35%) e diz se um defensivo cabia. Só o T07 (falha da IA) continua pendente, porque a IA entra no passo 5.

## 10.3 Resultado

Rodado em 04/11/2026 na `main`, com `pytest -q` em `backend/` (cerca de 20 s, sem internet).

| Total | Passaram | Falharam | Cobertura |
| ----- | -------- | -------- | --------- |
| 604   | 604      | 0        | Não medida (`pytest-cov` não está instalado no ambiente) |

Testes do motor de análise (126 no total), por arquivo em `backend/tests/`:

| Arquivo | Testes | O que cobre |
| --- | --- | --- |
| `test_engine_rules.py` | 39 | Regras do Mago Arcano (T03, T04, T11, T12) e o kill de referência |
| `test_engine_support.py` | 31 | Dano creditado ao Evocador Aumentação que apoiou o jogador |
| `test_engine_peaks.py` | 19 | Picos de dano e defensivos (T13) |
| `test_engine_base.py` | 17 | Fases, referência dos tops, tabelas por habilidade e por alvo (T05, T14) |
| `test_engine_timeline.py` | 7 | Janelas e acúmulos de buffs na linha do tempo |
| `test_engine_arcane_soul.py` | 5 | Entrada no Arcane Soul e Arcane Blast no Surge |
| `test_engine_report.py` | 5 | Montagem do `AnalysisResult` |
| `test_engine_prismatic_bolt.py` | 3 | Prismatic Bolt: decisão × sorte |

Além deles, `test_analyzer.py` (11) testa o `EngineAnalyzer`; os outros arquivos cobrem contas, rotas, fontes de dados, cliente do Warcraft Logs e busca dos tops.

_Inserir print da saída do `pytest -v`._

## 10.4 Testes do frontend

O frontend (React + Vite) tem três camadas de teste automatizado, todas com dados reais da API salvos em arquivo (`frontend/src/test/fixtures/`, só pseudônimos) e sem depender do backend, do Warcraft Logs ou da internet.

| Tipo | Ferramenta | Onde | O que cobre |
| --- | --- | --- | --- |
| Unidade | Vitest | `src/lib/*.test.js` | Funções puras e módulos de apoio: cliente da API e erros, validador de link (T01, T02), formatação, roteador por hash, tema, armazenamento com falha |
| Componente | Vitest + Testing Library | `src/components/*.test.jsx` | Cada componente isolado: estados, textos em português, teclado e atributos ARIA |
| Integração das telas | Vitest + Testing Library, com a API simulada (`src/test/mockApi.js`) | `src/pages/*.test.jsx`, `src/App.test.jsx` | Cada tela conversando com a API: caminhos, corpos, cabeçalho `Authorization`, erros por `code` (item 12.3), limite do plano, RF25 |
| Acessibilidade | axe-core | dentro dos testes acima e em `e2e/theme.spec.js` | No jsdom, regras do axe (sem contraste, que o jsdom não calcula); no navegador, o axe completo, com contraste |
| Tema e paletas | Vitest e Playwright | `src/theme-contrast.test.js`, `src/lib/theme.test.js`, `e2e/theme.spec.js` | Contraste WCAG AA dos tokens das duas paletas (`docs/15`), script do `index.html` igual ao `theme.js`, tema no navegador |
| Ponta a ponta | Playwright (Chromium) | `frontend/e2e/` | O site construído (`npm run build` + `preview`) num navegador de verdade, com a API simulada por `page.route` |

**Testes ponta a ponta (Playwright).** `e2e/flows.spec.js` percorre os fluxos principais: colar o link do kill de referência, lista de lutas (indisponíveis em cinza, com o motivo), escolher a luta e o Mago, pré-busca, análise com o corpo certo e resultado com a diferença para os tops, nomes ocultos (RF25) e aviso de exemplo; link inválido, Warcraft Logs fora do ar (`wcl_unavailable`), relatório privado, falha ao buscar os Magos, login, cadastro, sessão vencida e limite do plano (`plan_limit`, T08). `e2e/theme.spec.js` cobre o que o jsdom não consegue: primeira visita seguindo o sistema (claro e escuro) com a cor de fundo computada igual ao token, botão de alternar, escolha salva no reload e acima do sistema, ausência de flash (o `data-theme` já está certo antes de o React rodar, com o bundle segurado), `localStorage` bloqueado, celular 360×740 sem rolagem horizontal, e o axe-core com a regra de contraste ligada nas duas paletas em sete telas (início, login, cadastro, planos, escolher luta, resultado, resultado com nomes à mostra), exigindo zero violações sérias ou críticas.

Como rodar:

```bash
cd frontend
npm install
npm test                          # Vitest (unidade, componente, telas)
npx playwright install chromium   # só na primeira vez (baixa o navegador)
npm run test:e2e                  # Playwright; sobe o build sozinho na porta 4173
npm run lint
```

### Resultado (07/11/2026, branch `feat/tema-claro-escuro`)

| Suíte | Arquivos | Testes | Passaram | Falharam | Duração |
| --- | --- | --- | --- | --- | --- |
| Vitest (`npm test`) | 30 | 520 | 520 | 0 | ~10 s |
| Playwright (`npm run test:e2e`) | 2 | 43 | 43 | 0 | ~15 s |

Vitest por pasta: `src/lib` (9 arquivos), `src/components` (13), `src/pages` (6) e `src/` (2: `App.test.jsx`, `theme-contrast.test.js`). O Playwright rodou verde e estável em 3 rodadas seguidas. O Vitest roda com fuso fixo (`TZ=America/Sao_Paulo`, em `vite.config.js`), para datas e horas saírem iguais em qualquer máquina e no CI.

**CI** (`.github/workflows/ci.yml`, Node 22): o job do frontend roda lint, Vitest e build em Ubuntu e Windows; o job `frontend-e2e` roda o Playwright só no Ubuntu (o navegador é o mesmo nos dois sistemas e o download pesa), com `retries: 1` e os rastros de falha anexados como artefato.
