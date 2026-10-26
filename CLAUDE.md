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
| `backend/app/services/sources.py` | Interfaces `ReportSource` e `Analyzer`; hoje leem `app/samples/` (exemplo montado à mão). É aqui que o motor e o cliente do WCL entram |
| `backend/app/models.py`, `db.py`, `config.py`, `security.py` | Tabelas (`User`, `Analysis`), conexão, configurações do `.env` e login |
| `backend/app/engine/`, `ai/` | **Vazios — é o que falta construir** |
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
- **Barrage com menos de 12 stacks de Arcane Salvo** é erro quando vira hábito (limites no YAML). Chegar no cap (25) não é erro.
- A IA **não** consulta o Warcraft Logs nem faz contas; todo número vem do código.
- Relatório e interface em português (nomes do cliente pt-BR). Conversas com o Arthur sobre o jogo podem usar os nomes em inglês.
- **Nomes dos outros jogadores ocultos por padrão (RF25)**, com botão para exibir (como "ocultar saldo" de banco). O jogador analisado **nunca** é ocultado. Fixtures no repo só com pseudônimos; nomes reais nunca vão para a IA.

## Dados de referência para testes e demo

- Kill de referência: report `XhrmBaYkGCAQjH2D`, luta 34 (Nek'zali Mítico, 6:55), jogador **Harmonist** (Arcano, ilvl 327, bracket 326–328).
- IDs: encontro 3470, zona de ranking 53. Buffs: Arcane Salvo 1242974, Clearcasting 263725, Prismatic Bolt (proc) 1295942.
- Plano B da demo: guardar esse kill e os top 10 do bracket em arquivo (fixtures) para rodar sem internet.

## Próximos passos (ordem)

1. ~~Cliente da API do Warcraft Logs + script que salva fixtures do kill de referência e do top 10.~~ Feito.
2. **Alinhar a PR #2 (contas e telas, Pedro) ao contrato atual.** Ela foi feita antes do cliente do WCL e do RF25; nos conflitos, vale o que está neste arquivo. Fazer antes do motor plugar, para o contrato mudar uma vez só.
   - **RF25 no contrato.** *Onde:* `backend/app/schemas.py` (`PlayerOption`, `PlayerInfo` e uma lista dos jogadores comparados em `Comparison`) e `backend/app/samples/analysis_*.json`. *O quê:* cada jogador com `display_name` (pseudônimo, mesma função de `wcl/anonymize.py`) e `name` (real, ou nulo no modo demo sem `names.local.json`); o analisado com os dois iguais. *Por quê:* hoje só existe `name`, e o RF25 pede nomes dos outros ocultos por padrão.
   - **Botão de olho.** *Onde:* `frontend/src/pages/Result.jsx` (escolha salva com `lib/storage.js`). *O quê:* mostra/oculta os nomes dos comparados; oculto por padrão; desabilitado se `name` vier nulo; o analisado nunca é ocultado. *Por quê:* RF25; a tela de resultado ainda não lista os comparados.
   - **Jogador por nome + reino.** *Onde:* `schemas.py` (`PlayerOption`, `AnalysisRequest`), `api/analyses.py` (busca do jogador na luta) e `pages/ChooseFight.jsx`. *O quê:* enviar e casar o reino (ou o id do ator do WCL) além do nome. *Por quê:* hoje casa só pelo nome; `wcl/fetch.find_player` usa nome + reino porque o mesmo nome se repete entre reinos.
   - **Configuração única.** *Onde:* `app/config.py` e `app/wcl/client.py`. *O quê:* `WCL_CLIENT_ID`/`WCL_CLIENT_SECRET` em `Settings`, `env_file` com caminho absoluto (`backend/.env`), `WclClient.from_env` lendo `get_settings()` e sair o `python-dotenv`. *Por quê:* hoje dois códigos leem o `.env`, e o `Settings` depende da pasta de onde o uvicorn sobe.
   - **`WclReportSource`.** *Onde:* `app/wcl/queries.py` e `app/services/sources.py`. *O quê:* consulta das lutas e dos Magos Arcanos do report inteiro, mapeada para `ReportResolved`; trocar `get_report_source()` e apagar `samples/report_*.json`. *Por quê:* `FIGHT_META` busca uma luta só, e o `/reports/resolve` precisa do report inteiro; o exemplo atual é montado à mão.
   - **Eixo do tempo.** *Onde:* `docs/12` (12.9) e `schemas.py` (`TimelineTrack`). *O quê:* manter a `timeline` em segundos desde o início da luta e documentar a conversão a partir da fase. *Por quê:* o motor trabalha por fase (passo 2 do fluxo); sem isso, motor e telas podem usar eixos diferentes.
   - **Ajustes menores.** *Onde:* `api/deps.py`, `pages/Result.jsx`, `config.py`. *O quê:* token vencido não dá 401 em rota pública (tratar como sem login); `Result.jsx` chama `logout()` no `invalid_token`; `JWT_SECRET` obrigatório em produção. *Por quê:* hoje um token vencido bloqueia até a análise sem conta, e sem a chave o backend sobe com uma temporária.
3. Motor: leitura dos YAML, regras (Surge/Touch, poção, tempo ativo, Salvo no Barrage), tabela por habilidade. Entra como `Analyzer` em `services/sources.py`.
4. Pacote da IA + chamada ao Gemini + resposta reserva.
5. ~~Endpoints `POST /reports/resolve` e `POST /analyses`~~ Feitos na PR #2 (mais contas, histórico e limite de 5 análises/mês), ainda com dados de exemplo. O que falta (RF25, fonte real) está no passo 2.
6. ~~Frontend~~ Feito na PR #2: início → login → escolher luta/personagem → resultado, mais perfil e planos. Falta o botão de olho (passo 2).
7. Testes Pytest com as fixtures (casos no item 10): faltam T03–T05, T07 e T11–T14; T01, T02, T06 e T08–T10 já passam com os dados de exemplo.

## Como trabalhar neste repo

- Commits em português, no padrão `tipo(escopo): descrição` (feat, fix, docs, chore, test).
- Ao mudar o motor, atualizar `docs/12-documentacao-tecnica.md` junto.
- Erros da API sempre com `api_error(status, code, message)` (`app/errors.py`): `code` fixo para o frontend e `message` pronta em português (lista de códigos no item 12.3).
- Dados de exemplo aparecem com aviso amarelo (`"sample": true` / `"source": "exemplo"`); o que vier do motor real sai com `"source": "motor"`.
- Depois de um pull que mude o `pyproject.toml`, rodar `pip install -e ".[dev]"` de novo.
- Nada de chave, token ou dado pessoal no repositório (é público).
