# 12. Documentação de Desenvolvimento (Técnica)

> Em construção junto com o código.

## 12.1 Como rodar localmente

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Linux/macOS
.venv\Scripts\Activate.ps1                          # Windows (PowerShell)
pip install -e ".[dev]"
cp .env.example .env   # preencher as chaves (no PowerShell: Copy-Item .env.example .env)
uvicorn app.main:app --reload   # http://localhost:8000/health e /docs
# Depois de um git pull que mude o pyproject.toml, rode o pip install de novo.

# Frontend
cd frontend
npm install
npm run dev   # http://localhost:5173 (precisa do backend rodando)
```

## 12.2 Variáveis de ambiente

| Variável | Para quê |
|---|---|
| `WCL_CLIENT_ID` / `WCL_CLIENT_SECRET` | Acesso à API do Warcraft Logs |
| `DATA_SOURCE` | `wcl` (relatórios reais) ou `exemplo` (arquivos de `app/samples/`, sem internet: plano B da demo e CI). Vazio = `wcl` se houver as chaves do WCL, senão `exemplo`. `wcl` sem as chaves não sobe |
| `APP_ENV` | `dev` (padrão) ou `prod`. Em `prod` o backend não sobe sem `JWT_SECRET` |
| `NAMES_FILE` | Mapa pseudônimo → nome real do modo exemplo (RF25). Padrão: `tests/fixtures/names.local.json`, fora do git |
| `GOOGLE_CLOUD_PROJECT` | Projeto do Google Cloud (Vertex AI) |
| `DATABASE_URL` | Banco (SQLite em dev, PostgreSQL em produção). Vazio = `backend/logcoach.db`; caminho SQLite relativo (`sqlite:///./x.db`) é resolvido a partir de `backend/`, não da pasta de onde o uvicorn sobe. O arquivo é criado sozinho na primeira subida |
| `JWT_SECRET` | Assinatura do login. Vazio em dev = chave temporária (o login cai a cada reinício); obrigatório com `APP_ENV=prod` |

## 12.3 Endpoints da API

Documentação interativa em http://localhost:8000/docs (botão **Authorize** recebe o token do login).

| Método | Rota | Login | Descrição |
|---|---|---|---|
| POST | `/auth/register` | — | Cadastro com e-mail e senha (mín. 8 caracteres). Devolve o token |
| POST | `/auth/login` | — | Login. Devolve o token (JWT, vale 7 dias) |
| GET | `/me` | sim | E-mail, plano e análises usadas no mês |
| PUT | `/me/password` | sim | Troca a senha |
| DELETE | `/me` | sim | Exclui a conta e todas as análises (RNF07) |
| GET | `/me/analyses` | sim | Histórico, da mais recente para a mais antiga (RF12) |
| POST | `/reports/resolve` | — | Recebe o link, valida (RF03) e devolve as lutas e os Magos Arcanos (RF04) |
| POST | `/analyses` | opcional | Roda a análise de uma luta. Com login, guarda no histórico e conta no limite de 5/mês (RF14) |
| GET | `/analyses/{id}` | opcional | Resultado de uma análise. Análise de uma conta só abre para o dono |

**Erros.** Toda resposta de erro vem como `{"detail": {"code": "...", "message": "..."}}`. O `code` é fixo (o frontend decide o que fazer por ele) e a `message` já é o texto do item 8.2, pronto para mostrar ao usuário. Códigos: `invalid_link`, `report_not_available`, `fight_not_found`, `fight_too_short`, `unsupported_fight`, `no_arcane_mage`, `player_ambiguous`, `plan_limit`, `analysis_not_available`, `email_taken`, `invalid_credentials`, `wrong_password`, `login_required`, `invalid_token`, `analysis_not_found`.

**Análise sem conta (RF01).** O backend aceita a análise sem login, mas não a coloca em histórico nenhum. O limite de 1 análise de demonstração é controlado no navegador; controlar no servidor fica para a publicação (item 13).

**Escolha do jogador.** `POST /analyses` recebe `player_name` e `server` (reino, pode ser nulo). Nome único na luta basta; com reino informado e diferente do conhecido, é outro personagem (`no_arcane_mage`). Nome repetido sem reino que desempate dá `player_ambiguous`. Regra em `services/players.py` (`match_player`), com a mesma normalização de reino do `wcl/fetch.find_player`.

**Login em rota pública.** Em rotas com login opcional, token inválido ou vencido vale como "sem login". Só as rotas que exigem login respondem `invalid_token`. Por isso o frontend confere a sessão salva com `GET /me` ao abrir o site e sai da conta se o token venceu; se uma análise feita com login volta com `saved: false`, ele também sai da conta.

**Limite do plano.** Conta por mês do calendário em UTC: as análises feitas desde o dia 1º às 00:00 UTC.

### De onde vêm os dados

As rotas não falam direto com o Warcraft Logs nem com o motor. Elas dependem de duas interfaces em `backend/app/services/sources.py`:

| Interface | O que faz | Implementação atual |
|---|---|---|
| `ReportSource.get_report(code)` | Lista as lutas e os Magos Arcanos de um relatório | `WclReportSource` (`DATA_SOURCE=wcl`): uma consulta `REPORT_FIGHTS` (~2 pontos) a cada chamada; ainda sem cache. `SampleReportSource` (`DATA_SOURCE=exemplo`): lê `app/samples/report_<código>.json` (só o kill de referência) |
| `Analyzer.analyze(report, fight, player)` | Devolve o resultado da análise | `SampleAnalyzer`: lê `app/samples/analysis_<código>_<luta>.json` |

Os arquivos de exemplo são marcados como exemplo (`"sample": true` e `"source": "exemplo"`) e a interface mostra um aviso amarelo. O `WclReportSource` já lê relatórios reais; o analisador ainda é o de exemplo, então só a luta de referência, e só para o Harmonist, tem resultado (outras lutas ou outros Magos dão `analysis_not_available`, sem gravar no histórico). O exemplo foi refeito em 28/10 a partir do log real (fixtures com buffs externos): só o impacto em % das regras e o tempo ativo são ilustrativos (ver `_nota` do arquivo). A soma dos `impact_pct` fecha com a diferença de DPS: o que as regras não explicam fica no erro `hipotese` (RF23), e `tests/test_samples.py` confere isso. Quando o motor ficar pronto, basta trocar o que `get_analyzer()` devolve. Nenhuma rota nem tela muda.

No `WclReportSource`: entram só Magos com spec Arcano; spec e item level vêm do `playerDetails` da noite inteira (o motor confere a spec na luta escolhida); chefe suportado = encontro com YAML em `encounters/`, dificuldade listada em `difficulties` do YAML (Nek'zali: só Mítico) e luta de 60 s ou mais; chefe e dificuldade em pt-BR (`pt_br.yaml`). Erro do WCL ou report privado viram `report_not_available`; o link de exemplo (`XhrmBaYkGCAQjH2D`) abre mesmo com o WCL fora do ar (plano B da demo). Consulta conferida no report de referência.

**Nomes na resposta (RF25).** Em `POST /analyses` e `GET /analyses/{id}`, cada jogador comparado vem em `comparison.players` (hoje o top 10; o 1º geral do RF21 e os colegas de raide entram com o motor) com `display_name` (pseudônimo estável: `top01`… pela posição no ranking, `raid_01`… pela ordem de ID; a tela mostra "Top 1", "Raide 1") e `name` (nome real, ou nulo quando não há). O jogador analisado vem com `display_name` = `name`. Quem decide o que mostrar é o frontend. A IA recebe só os pseudônimos: os nomes reais nunca entram no pacote da IA.

## 12.4 Motor de análise: as três camadas de regras

| Camada | O que é | Exemplos | Onde fica |
|---|---|---|---|
| **1. Regras da especialização** (determinísticas) | Valem em qualquer luta | Tempo parado, quantas vezes cada cooldown foi usado vs. o máximo possível, recurso desperdiçado, procs perdidos, mortes | `backend/app/rules/arcane_mage.yaml` |
| **2. Regras do encontro** (determinísticas) | Descrevem a luta, uma por chefe | Fases e intermissões, janelas de burst esperadas, golpes de raide (onde se espera defensivo), períodos em que o chefe não pode ser atacado | `backend/app/encounters/nekzali.yaml` |
| **3. Perguntas de julgamento** (IA) | O que não vira regra fixa | "Valeu segurar o cooldown para a próxima fase?", "o erro se repete em todos os pulls?", "é erro de execução ou de planejamento?" | Prompt do coach (item 9) |

A camada 2 **ajusta** a camada 1. Exemplo: tempo parado durante uma intermissão não conta como erro; um cooldown segurado para uma janela de burst mais valiosa conta como acerto.

## 12.5 Como o sistema relaciona os eventos do chefe com os cooldowns do jogador

1. **Relógio único.** Pela API do Warcraft Logs são buscados os eventos da luta: casts do chefe, casts e buffs do jogador, dano recebido, mortes e transições de fase. Todo horário vira "segundos desde o início da luta".
2. **Linha do tempo do encontro.** Com o YAML do chefe, o sistema marca as fases, as janelas de burst e os golpes de raide, identificando cada habilidade do chefe pelo seu ID.
3. **Cruzamento.** Para cada janela, verifica se o cooldown do jogador caiu dentro dela (com tolerância de alguns segundos). Para cada golpe de raide, verifica se havia defensivo ativo.
4. **Com quem comparar.** Os 10 melhores logs da mesma especialização, chefe e dificuldade **dentro da faixa de item level do jogador** (o "bracket" do Warcraft Logs, de 3 em 3 níveis: 326–328, 329–331…). Assim a diferença mostrada é de execução, não de equipamento. Se o jogador já estiver nesse top 10, o relatório reconhece e compara com o 1º colocado geral.
5. **Comparação por fase.** Como cada luta tem duração diferente, o sistema compara "X segundos após o início da fase" do jogador com o mesmo ponto nos melhores logs, e não o tempo absoluto.
6. **Saída.** Um JSON de fatos (ex.: "CD principal usado 2 de 4 vezes possíveis; 1 fora de janela de burst na fase 2") vai para a IA, junto com as perguntas da camada 3.

## 12.6 O que a IA recebe

A IA não consulta o Warcraft Logs nem faz conta. O backend monta um pacote com três partes:

| Parte | O que é | Quem produz |
|---|---|---|
| **Fatos das regras** | Erros conhecidos, com certeza (ex.: "4º Surge 4,5 s depois do Touch") | Motor, a partir dos YAML |
| **Guia da luta e da spec** | Texto curto: como o chefe funciona, como o Arcano joga, o que não é erro (`backend/app/guides/nekzali.md` e `arcane_mage.md`) | Arthur (um por chefe e um por spec) |
| **Tabela por habilidade** | Por fase: casts por minuto e % do dano de cada habilidade, jogador vs. média dos top 10 do mesmo bracket | Motor (RF22), genérico para qualquer spec |

Com isso a IA ordena os erros, explica em português e aponta como **hipótese** o que destoar na tabela sem ter regra (RF24). A tabela usa casts **por minuto** porque a duração das fases muda entre kills.

**Idioma.** Os nomes de habilidades, adds e fases chegam do Warcraft Logs em inglês. O motor troca pelo nome em português do cliente do jogo usando `backend/app/i18n/pt_br.yaml` (por ID), antes de montar o pacote. Assim a IA e o relatório falam a língua do jogador brasileiro.

**Diferença não explicada (RF23).** Se o jogador fez, por exemplo, 25% menos dano que os tops no Stage Two e as regras só explicam parte disso, o motor marca a sobra. É um sinal para a IA olhar a tabela daquela fase com mais atenção.

**Do achado à regra.** As hipóteses da IA ficam registradas. O Arthur revisa e, se for um padrão de verdade, ele vira regra no YAML e passa a ser checado de graça em toda análise.

**Fora do MVP:** dar à IA ferramentas para consultar o log por conta própria. Fica para depois da banca, se o custo e o limite da API permitirem.

### Métricas da comparação (Mago Arcano)

| Métrica | Exemplo no kill de referência |
|---|---|
| Cadência do Arcane Surge | Tops do bracket: ~93 s entre usos |
| Distância Touch → Surge | Tops: 0,1 a 3,2 s |
| Momento da 2ª poção | 9 de 10 tops: entre 4:59 e 5:29 |
| Defensivo nos overlaps | Ver `overlaps` em `nekzali.yaml` |
| DPS por fase | Stage Two é onde a diferença costuma aparecer |

**Cache por bracket (RNF03):** a referência dos top 10 é a mesma para todos do mesmo chefe, dificuldade e bracket, então é calculada uma vez a cada 24 h e reaproveitada.

## 12.7 Formato dos arquivos de regras (rascunho)

```yaml
# backend/app/encounters/nekzali.yaml
encounter: Nek'zali the Soulcoiler
encounter_id: 0          # TODO: ID do Warcraft Logs
phases:                  # vindas das transições de fase do log
  - id: 1
    name: Fase 1
  - id: 2
    name: Fase 2
untargetable:            # períodos que não contam como tempo parado
  - name: Intermissão     # TODO: definir início/fim pelo evento correto
    start_event: { ability_id: 0 }
    end_event: { ability_id: 0 }
burst_windows:           # onde se espera cooldown ofensivo
  - name: Início da Fase 2
    phase: 2
    offset_s: 0
    duration_s: 20       # TODO: validar
raid_hits:               # onde se espera defensivo
  - name: Golpe de raide  # TODO
    ability_id: 0
```

```yaml
# backend/app/rules/arcane_mage.yaml
spec: Arcane Mage
cooldowns:
  - name: CD principal    # TODO: feitiço e ability_id
    ability_id: 0
    cooldown_s: 0
    expect_in_burst_windows: true
defensives:
  - name: Defensivo       # TODO
    ability_id: 0
thresholds:
  downtime_pct: { warn: 3, error: 6 }   # TODO: calibrar com os top logs
```

> Feitiços, IDs, janelas e limites: definidos e validados pelo Arthur.

## 12.8 Cliente do Warcraft Logs e fixtures

Código em `backend/app/wcl/`.

| Arquivo | O que faz |
|---|---|
| `client.py` | `WclClient` (`from_env()` lê as chaves do `Settings`, em `app/config.py`): troca `WCL_CLIENT_ID` + `WCL_CLIENT_SECRET` por um token (fluxo *client credentials*), guarda o token e renova sozinho quando vence ou quando a API responde 401. `query()` faz o POST GraphQL; `events()` segue a paginação (`nextPageTimestamp`). |
| `queries.py` | Consultas GraphQL: lutas e jogadores do report (`REPORT_FIGHTS`), dados da luta, brackets do encontro, rankings. |
| `fetch.py` | `fetch_report()` devolve as lutas e os jogadores do report (usado pelo `WclReportSource`); `fetch_fight()` devolve uma luta pronta para o motor; `fetch_rankings()` e `bracket_index()` acham os top N do bracket. |
| `anonymize.py` | Troca os nomes de jogadores por pseudônimos antes de salvar. |

**Limite da API:** 1000 pontos por hora. Uma luta completa custa ~12 pontos; o kill de referência + top 10 custa ~130.

**Formato de uma luta** (`fetch_fight`). Os tempos ficam em **ms do report**, como vêm da API. A conversão para "segundos desde o início da fase" é do motor, usando `meta.fight.phaseTransitions`.

| Chave | Conteúdo |
|---|---|
| `meta` | Código do report, `fight` (id, encontro, dificuldade, kill, início/fim, `phaseTransitions`), `duration_ms` |
| `phases` | Nomes das fases do encontro (`id`, `name`, `isIntermission`) |
| `actors`, `abilities` | Só os que aparecem nos eventos desta luta |
| `player` | Ator do jogador + `details` (spec, `minItemLevel`/`maxItemLevel`) |
| `events.casts` | Casts do jogador (`begincast` e `cast`) |
| `events.buffs` | Buffs no jogador, com stacks (`applybuffstack`/`removebuffstack` trazem `stack`) |
| `events.damage_done` | Dano do jogador (sem a lista de buffs por golpe, que já está em `buffs`) |
| `events.damage_taken`, `events.deaths` | Dano recebido e mortes do jogador (defensivo nos overlaps) |
| `events.boss_casts` | Casts dos inimigos (habilidades do chefe e dos adds do `nekzali.yaml`) |

**Fixtures.** `cd backend && python scripts/save_fixtures.py` baixa o kill de referência e os top 10 do mesmo bracket para `tests/fixtures/nekzali_mythic_<min>_<max>/` (`--only-reference` só a referência, `--force` para sobrescrever). Cada luta é um `.json.gz`; o `index.json` lista o bracket e o DPS/duração de cada top. Servem para os testes, para desenvolver sem internet e como plano B da demo.

**Nomes ocultos por padrão.** O repositório é público, então os arquivos versionados não têm nome, reino, GUID, guilda nem código de report dos outros jogadores: o analisado vira `top01`…`top10` e o resto da raide `raid_01`…. Cada ator ganha `display_name`. O mapa com os dados reais fica em `tests/fixtures/names.local.json` (no `.gitignore`).

**Na aplicação (RF25).** Os pseudônimos dos fixtures são os mesmos que a API devolve em `display_name` (ver 12.3 e 12.9), gerados pela mesma função de `anonymize.py`. Com dados ao vivo, o `name` real vem direto do Warcraft Logs. No modo demo (sem internet, lendo os fixtures), o `name` vem do `names.local.json` se ele existir na máquina (caminho em `NAMES_FILE`; `SampleAnalyzer` usa `fill_real_names`); se não existir, `name` vem nulo e o botão de mostrar nomes fica desabilitado. O jogador analisado nunca é ocultado.

## 12.9 Formato do resultado da análise (contrato motor ↔ telas)

O motor devolve um `AnalysisResult` (`backend/app/schemas.py`); o frontend só lê desse objeto. Exemplo completo em `backend/app/samples/analysis_XhrmBaYkGCAQjH2D_34.json`.

| Campo | O que é | Requisito |
|---|---|---|
| `source` | `"exemplo"` ou `"motor"` | — |
| `fight`, `player` | Chefe, dificuldade, kill/wipe, duração; nome, reino (`server`), `display_name` (= `name`: o analisado nunca é ocultado), spec e item level | RF25 |
| `comparison` | Com quem comparou (`label`, `bracket`, `size`), se o jogador já está no top 10 e `players`: cada comparado com `rank`, `display_name` (`top01`…), `name` (real, ou nulo no modo exemplo), `server`, `item_level` e `dps` | RF21, RF25 |
| `summary` | DPS do jogador, média dos tops, diferença em %, tempo ativo | RF08 |
| `coach` | `available` falso quando a IA falhou; `headline` é o resumo do coach | RF17 |
| `mistakes` | Erros **já ordenados**: primeiro os de regra, do maior para o menor impacto (risco, com `impact_pct` nulo, no fim); depois as hipóteses. Na hipótese, `impact_pct` é a diferença que nenhuma regra explica (RF23), e o texto traz as pistas do coach (RF24); a tela mostra as hipóteses numa seção à parte, "O que as regras não explicam", sem posição e sem "custou X%". Cada um: `title`, `impact_pct` (ou `null` se é risco, não dano), `severity` (`atencao`/`erro`), `kind` (`regra` ou `hipotese`), `phase`, `explanation`, `what_to_do` e `numbers` (você × melhores) | RF10, RF24 |
| `rules` | Todas as regras checadas, com valor do jogador, dos melhores e `status` (`ok`/`atencao`/`erro`) | RF07, RF18 |
| `phases` | Fases com início e fim em segundos e se é intermissão | RF20 |
| `timeline` | Por cooldown: segundos **desde o início da luta** de cada uso do jogador (`player_s`) e do log de referência dos tops (`top_s`). O motor calcula por fase e converte com `phases[].start_s` | RF11 |
| `abilities` | Por fase: casts por minuto e % do dano, jogador × tops | RF22 |

Os textos (`title`, `explanation`, `what_to_do`) saem em português, com os nomes de `pt_br.yaml`.

## 12.10 Motor: Prismatic Bolt, decisão × sorte

A spec do Arcano depende muito de RNG: a Prismatic Bolt (Seta Prismática) vem de procs do Arcane Barrage. Para não cobrar azar como erro, o motor separa as duas coisas (`backend/app/engine/prismatic_bolt.py`, regra `prismatic_bolt_rng` em `arcane_mage.yaml`).

| Medida | Como é calculada | O que mostra |
|---|---|---|
| Esperado | Soma, em cada Barrage, de 2% × acúmulos de Salvo naquele instante | A **decisão**: soltar Barrage com poucos acúmulos baixa a chance |
| Recebidos | Barrages seguidos de proc em até 0,5 s | O que aconteceu |
| Sorte (z) | (recebidos − esperado) ÷ √Σ p(1 − p) | O **RNG**: abaixo de −2 é azar, acima de +2 é sorte |

**Validação (28/10/2026).** Nos 1.015 Barrages das 11 fixtures, a taxa de proc por faixa de Salvo bate com 2% por acúmulo (10–14: 26%; 15–19: 35%; 20–24: 45%; 25: 53%); o ajuste dá 2,1% por acúmulo. No kill de referência, o Harmonist esperava ~41 procs (5,9 por minuto, contra 6,2 dos tops) e recebeu 28: z = −2,8. Os tops tiveram z +0,9 em média, e um deles +3,5. As Salvas soltas cedo explicam só cerca de 10% da falta de Seta; o resto foi azar. Um ranking de melhores logs tende a escolher lutas com sorte, e o relatório precisa dizer isso.

