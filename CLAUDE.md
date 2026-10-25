# LogCoach — contexto para o Claude Code

Trabalho A3 de Usabilidade de Software (Engenharia de Software, UNA). Web app que analisa o log de combate do World of Warcraft (Warcraft Logs) de um **Mago Arcano** e explica, em português, o que ele errou, comparando com os 10 melhores do mesmo item level.

- **RT03: 28/10/2026** — meta: versão alfa rodando com o chefe Nek'zali (Mítico).
- **Banca final:** fim de novembro.
- **Líder técnico e especialista do jogo:** Arthur (joga em inglês; produto sai em português).

## Stack

- Backend: FastAPI (Python) em `backend/` — `uvicorn app.main:app --reload`
- Frontend: React + Vite em `frontend/` — `npm run dev`
- IA: Gemini via Vertex AI (Google Cloud)
- Dados: API v2 do Warcraft Logs (GraphQL). Chaves só no `backend/.env` (ver `.env.example`), nunca no código.
- Como rodar: `docs/12-documentacao-tecnica.md` (12.1).

## Onde está cada coisa

| Caminho | O que é |
|---|---|
| `docs/01..14-*.md` | Documentação do GitBook (escopo, requisitos, arquitetura, plano, IA, testes…) |
| `docs/04-documento-de-requisitos.md` | RF01–RF24 e RNFs |
| `docs/12-documentacao-tecnica.md` | Arquitetura do motor e o que a IA recebe |
| `backend/app/rules/arcane_mage.yaml` | Regras do Arcano (Surge/Touch, Salvo no Barrage, poção, limites, IDs de magias e buffs) |
| `backend/app/encounters/nekzali.yaml` | Regras do chefe (fases, intermissão, overlaps de dano, esperas aceitas) |
| `backend/app/guides/*.md` | Guias em português que vão para a IA como contexto |
| `backend/app/i18n/pt_br.yaml` | Nome em português de cada magia/NPC por ID |
| `backend/app/engine/`, `ai/`, `api/` | **Vazios — é o que falta construir** |

## Fluxo do motor (o que construir)

1. Buscar a luta do jogador e os **top 10 do mesmo bracket de item level** (cache de 24 h por chefe + dificuldade + bracket).
2. Montar a linha do tempo em "segundos desde o início da fase" (fases vêm prontas do Warcraft Logs).
3. Aplicar as regras dos dois YAML → **fatos** (erros com certeza).
4. Montar a **tabela por habilidade e por fase** (casts/min e % do dano, jogador vs. média dos top 10) — RF22. Marcar diferença não explicada — RF23.
5. Traduzir nomes com `pt_br.yaml`.
6. Enviar à IA o pacote: fatos + guias + tabela (nunca o log bruto). IA ordena, explica e aponta hipóteses (RF24).
7. Se a IA falhar, relatório só com as regras (RF17).

## Decisões já tomadas (não reabrir sem falar com o Arthur)

- Comparação só com o **mesmo bracket de item level** do Warcraft Logs (faixas de 3 níveis). Se o jogador já está no top 10, compara com o 1º geral (RF21).
- **Defensivo só é cobrado em overlap** de mecânicas; mecânica isolada não pede defensivo.
- Surge em recarga; segurar até ~15 s só para casar com poção, Time Warp ou fase do chefe.
- **Barrage com menos de 12 stacks de Arcane Salvo** é erro quando vira hábito (limites no YAML). Chegar no cap (25) não é erro.
- A IA **não** consulta o Warcraft Logs nem faz contas; todo número vem do código.
- Relatório e interface em português (nomes do cliente pt-BR). Conversas com o Arthur sobre o jogo podem usar os nomes em inglês.

## Dados de referência para testes e demo

- Kill de referência: report `XhrmBaYkGCAQjH2D`, luta 34 (Nek'zali Mítico, 6:55), jogador **Harmonist** (Arcano, ilvl 327, bracket 326–328).
- IDs: encontro 3470, zona de ranking 53. Buffs: Arcane Salvo 1242974, Clearcasting 263725, Prismatic Bolt (proc) 1295942.
- Plano B da demo: guardar esse kill e os top 10 do bracket em arquivo (fixtures) para rodar sem internet.

## Próximos passos (ordem)

1. Cliente da API do Warcraft Logs + script que salva fixtures do kill de referência e do top 10.
2. Motor: leitura dos YAML, regras (Surge/Touch, poção, tempo ativo, Salvo no Barrage), tabela por habilidade.
3. Pacote da IA + chamada ao Gemini + resposta reserva.
4. Endpoints `POST /reports/resolve` e `POST /analyses` (ver item 12.3).
5. Frontend com 3 telas: colar link → escolher luta/personagem → relatório.
6. Testes Pytest com as fixtures (casos no item 10).

## Como trabalhar neste repo

- Commits em português, no padrão `tipo(escopo): descrição` (feat, fix, docs, chore, test).
- Ao mudar o motor, atualizar `docs/12-documentacao-tecnica.md` junto.
- Nada de chave, token ou dado pessoal no repositório (é público).
