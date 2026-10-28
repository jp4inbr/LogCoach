# LogCoach — contexto para o Claude Code

Trabalho A3 de Usabilidade de Software (Engenharia de Software, UNA). Web app que analisa o log de combate do World of Warcraft (Warcraft Logs) de um **Mago Arcano** e explica, em português, o que ele errou, comparando com os 10 melhores do mesmo item level.

- **RT03: 28/10/2026** — meta: versão alfa rodando com o chefe Nek'zali (Mítico).
- **Banca final:** fim de novembro.
- **Líder técnico e especialista do jogo:** Arthur (joga em inglês; produto sai em português).

## Stack

- Backend: FastAPI (Python) em `backend/` — `uvicorn app.main:app --reload`
- Frontend: React + Vite em `frontend/` — `npm run dev`
- IA: Gemini via Vertex AI (Google Cloud)
- Banco: SQLModel (SQLite em dev, PostgreSQL em produção); tabelas criadas na subida, sem migrações. Login com JWT, senha com argon2.
- Dados: API v2 do Warcraft Logs (GraphQL). Chaves só no `backend/.env` (ver `.env.example`), nunca no código.
- Como rodar: `docs/12-documentacao-tecnica.md` (12.1).

## Onde está cada coisa

| Caminho | O que é |
|---|---|
| `docs/01..14-*.md` | Documentação do GitBook (escopo, requisitos, arquitetura, plano, IA, testes…) |
| `docs/04-documento-de-requisitos.md` | RF01–RF25 e RNFs |
| `docs/12-documentacao-tecnica.md` | Como rodar, endpoints e erros (12.3), motor, o que a IA recebe, cliente do WCL (12.8) e contrato do resultado (12.9) |
| `backend/app/rules/arcane_mage.yaml` | Regras do Arcano (Surge/Touch, Salvo no Barrage, poção, limites, IDs de magias e buffs) |
| `backend/app/encounters/nekzali.yaml` | Regras do chefe (fases, intermissão, overlaps de dano, esperas aceitas) |
| `backend/app/guides/*.md` | Guias em português que vão para a IA como contexto |
| `backend/app/i18n/pt_br.yaml` | Nome em português de cada magia/NPC por ID |
| `backend/app/wcl/` | Cliente da API do Warcraft Logs, busca de luta/rankings e anonimização (item 12.8) |
| `backend/scripts/save_fixtures.py` | Baixa o kill de referência + top 10 para `backend/tests/fixtures/` |
| `backend/app/api/` | Rotas: contas (`/auth`, `/me`), `/reports/resolve` e `/analyses` (item 12.3) |
| `backend/app/schemas.py` | `AnalysisResult`: formato que o motor devolve e as telas leem (item 12.9) |
| `backend/app/services/sources.py` | Interfaces `ReportSource` e `Analyzer`. Relatório: `WclReportSource` (real) ou `SampleReportSource` (`app/samples/`), escolhido por `DATA_SOURCE`. Análise: ainda `SampleAnalyzer`; é aqui que o motor entra |
| `backend/app/services/players.py` | Escolha do jogador na luta por nome + reino (`match_player`, `normalize_server`) |
| `backend/app/models.py`, `db.py`, `config.py`, `security.py` | Tabelas (`User`, `Analysis`), conexão, configurações do `.env` e login |
| `backend/app/engine/` | Motor, começando: `rules.py` (lê os YAML), `timeline.py` (janelas e acúmulos de buffs), `prismatic_bolt.py` (Prismatic Bolt: decisão × sorte) e `arcane_soul.py` (entrada no Arcane Soul e Blast no Surge), item 12.10. O resto das regras falta |
| `backend/app/ai/` | **Vazio — é o que falta construir** |
| `frontend/src/pages/` | Telas: início, login, escolher luta, resultado, perfil, planos (roteamento por hash em `lib/router.js`, chamadas em `lib/api.js`) |

## Fluxo do motor (o que construir)

O motor entra como um `Analyzer` em `services/sources.py` e devolve um `AnalysisResult` (item 12.9); rotas e telas não mudam.

1. Buscar a luta do jogador e os **top 10 do mesmo bracket de item level** (cache de 24 h por chefe + dificuldade + bracket).
2. Montar a linha do tempo em "segundos desde o início da fase" (fases vêm prontas do Warcraft Logs). No `AnalysisResult`, a `timeline` sai em segundos desde o início da luta (convertido com `phases[].start_s`).
3. Aplicar as regras dos dois YAML → **fatos** (erros com certeza).
4. Montar a **tabela por habilidade e por fase** (casts/min e % do dano, jogador vs. média dos top 10) — RF22. Marcar diferença não explicada — RF23.
5. Traduzir nomes com `pt_br.yaml`.
6. Enviar à IA o pacote: fatos + guias + tabela (nunca o log bruto). IA ordena, explica e aponta hipóteses (RF24).
7. Se a IA falhar, relatório só com as regras (RF17).

## Decisões já tomadas (não reabrir sem falar com o Arthur)

- Comparação só com o **mesmo bracket de item level** do Warcraft Logs (faixas de 3 níveis). Se o jogador já está no top 10, compara com o 1º geral (RF21).
- **Defensivo só é cobrado em overlap** de mecânicas; mecânica isolada não pede defensivo.
- Surge em recarga; segurar até ~15 s só para casar com poção, Time Warp ou fase do chefe.
- **Segurar a 2ª poção para casar com o Surge é o recomendado**, não erro (Light's Potential junto do Surge rende mais que a poção no CD aos 5:00), desde que a luta dure o bastante para esse Surge. O erro é **atrasar o Surge** e dessincronizar o Touch.
- **Barrage com menos de 12 stacks de Arcane Salvo** é erro quando vira hábito (limites no YAML). Chegar no cap (25) não é erro. O motivo é o snowball de Meteorite (1 a cada 5 Salvo → Clearcasting → Missiles → Salvo), não a chance de Prismatic Bolt, que é linear (2% por Salvo).
- **Entrar no Arcane Soul com 25 de Salvo**: nada de Barrage nos 2 últimos GCDs antes do Soul, exceto com Overpowered Missiles (sobe para 25 na hora). No Soul o Barrage não gasta Salvo.
- **Clearcasting guardada para o Surge**, para não encher o burst de Arcane Blast.
- **Prismatic Bolt é RNG**: o relatório separa decisão (procs esperados pelos acúmulos) de sorte (desvios do esperado) e não cobra azar como erro.
- A IA **não** consulta o Warcraft Logs nem faz contas; todo número vem do código.
- Relatório e interface em português (nomes do cliente pt-BR). Conversas com o Arthur sobre o jogo podem usar os nomes em inglês.
- **Nomes dos outros jogadores ocultos por padrão (RF25)**, com botão para exibir (como "ocultar saldo" de banco). O jogador analisado **nunca** é ocultado. Fixtures no repo só com pseudônimos; nomes reais nunca vão para a IA.

## Dados de referência para testes e demo

- Kill de referência: report `XhrmBaYkGCAQjH2D`, luta 34 (Nek'zali Mítico, 6:55), jogador **Harmonist** (Arcano, ilvl 327, bracket 326–328).
- IDs: encontro 3470, zona de ranking 53. Buffs: Arcane Salvo 1242974, Clearcasting 263725, Prismatic Bolt (proc) 1295942.
- Plano B da demo: guardar esse kill e os top 10 do bracket em arquivo (fixtures) para rodar sem internet. Na aplicação, `DATA_SOURCE=exemplo` usa os arquivos de `app/samples/`.

## Próximos passos (ordem)

1. ~~Cliente da API do Warcraft Logs + script que salva fixtures do kill de referência e do top 10.~~ Feito.
2. ~~Alinhar a PR #2 (contas e telas, Pedro) ao contrato atual.~~ Feito: RF25 no contrato (`display_name`/`name`, `comparison.players`) e botão de olho no resultado, jogador por nome + reino (`player_ambiguous`), configuração única em `app/config.py` (`DATA_SOURCE`, `APP_ENV`), `WclReportSource`, `timeline` em segundos da luta, ajustes de login, Nek'zali só no Mítico e nomes reais do `names.local.json` no modo exemplo. Exemplo refeito em 28/10 a partir do log real (só o impacto em % das regras e o tempo ativo são ilustrativos); hipóteses numa seção à parte no resultado. Antes, as três pendências antigas da PR #2: exemplo só serve o Harmonist, banco SQLite sempre em `backend/logcoach.db` e exemplo com impactos que somam a diferença de DPS. `REPORT_FIGHTS` conferida na API real. Ficou:
   - **Cache e cliente único do WCL.** *Onde:* `app/services/sources.py` (`WclReportSource`, `get_report_source`). *O quê:* um `WclClient` por processo (o token se renova sozinho) e cache do `ReportResolved` por código (5–10 min). *Por quê:* hoje cada `/reports/resolve` e cada `/analyses` pede token novo e baixa o report de novo (~2 pontos de 1000/h).
   - **Jogador pelo id do ator do WCL.** *Onde:* `schemas.py` (`PlayerOption`, `AnalysisRequest`), `services/players.py`, `wcl/fetch.py` (`find_player`). *O quê:* levar o `actor_id` do `REPORT_FIGHTS` até o motor e casar por ele; trazer `normalize_server` para `app/wcl/`. *Por quê:* hoje há duas regras de nome + reino (`match_player` e `find_player`) e `wcl/fetch.py` importa de `services/` (camada invertida).
   - **Código de erro próprio para o WCL fora do ar.** *Onde:* `services/sources.py`, `api/reports.py`. *O quê:* `wcl_unavailable` para 429/5xx, separado de `report_not_available`. *Por quê:* hoje limite de pontos e API fora do ar aparecem como "confira se o relatório está público".
   - **Buffs externos no motor.** *Onde:* `app/rules/arcane_mage.yaml` (`external_buffs`) e o motor. *O quê:* contar Power Infusion e outros buffs de outros jogadores no jogador e em cada top e mostrar como contexto. *Por quê:* a busca já traz os externos (corrigida em 28/10; fixtures baixadas de novo). No kill de referência: Harmonist 2 PIs, tops 1,4 em média, o 1º colocado nenhum, ou seja, o PI não explica a diferença dele.
   - **Nomes em pt-BR conferidos no Wowhead.** *Onde:* `app/i18n/pt_br.yaml`, `app/guides/*.md`, `app/samples/*.json`. *O quê:* cruzar cada magia, buff e talento do inglês com o nome do cliente pt-BR no Wowhead (trocando o idioma da página) e padronizar. *Por quê:* há divergências; ex.: Clearcasting (263725) aparece como "Clarividência" no exemplo e "Clareza Mental" no guia, e no Warcraft Logs em português aparece "Abstração". "Abstração" e "Infusão de Poder" já entraram no `pt_br.yaml`, marcados para conferir.
   - `samples/report_*.json` **fica** como fonte offline (`DATA_SOURCE=exemplo` ou WCL fora do ar): plano B da demo e fonte do CI.
3. Motor: leitura dos YAML, regras (Surge/Touch, poção, tempo ativo, Salvo no Barrage), tabela por habilidade. Entra como `Analyzer` em `services/sources.py`. Já existem as peças de Prismatic Bolt (decisão × sorte) e de Arcane Soul/janela do Surge (`engine/`, item 12.10); os cálculos usados para refazer o exemplo em 28/10 (Salvo na Salva, atrasos, Surge→Touch, poção com Surge, picos com defensivo, tabela por habilidade) servem de base para as outras.
4. Pacote da IA + chamada ao Gemini + resposta reserva.
5. ~~Endpoints `POST /reports/resolve` e `POST /analyses`~~ Feitos (PR #2 + passo 2). `/reports/resolve` já lê relatórios reais; `/analyses` só tem resultado da luta de referência até o motor entrar.
6. ~~Frontend~~ Feito: início → login → escolher luta/personagem → resultado (com a lista dos comparados e o botão de olho), mais perfil e planos.
7. Testes Pytest com as fixtures (casos no item 10): faltam T03–T05, T07 e T11–T14; T01, T02, T06 e T08–T10 já passam com os dados de exemplo.

## Como trabalhar neste repo

- Commits em português, no padrão `tipo(escopo): descrição` (feat, fix, docs, chore, test).
- Ao mudar o motor, atualizar `docs/12-documentacao-tecnica.md` junto.
- Erros da API sempre com `api_error(status, code, message)` (`app/errors.py`): `code` fixo para o frontend e `message` pronta em português (lista de códigos no item 12.3).
- Dados de exemplo aparecem com aviso amarelo (`"sample": true` / `"source": "exemplo"`); o que vier do motor real sai com `"source": "motor"`.
- Depois de um pull que mude o `pyproject.toml`, rodar `pip install -e ".[dev]"` de novo.
- Nada de chave, token ou dado pessoal no repositório (é público).
