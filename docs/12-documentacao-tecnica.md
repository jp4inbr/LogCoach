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
| POST | `/reports/resolve` | — | Recebe o link, valida (RF03) e devolve a lista de lutas do report (sem jogadores), com `fetched_at`. Sempre busca a lista de novo no Warcraft Logs (colar o link, "Atualizar lutas" e a atualização automática usam a mesma chamada; `refresh` é aceito, mas não muda nada); menos de 8 s depois da última busca, devolve a lista guardada. Se o Warcraft Logs falhar e houver lista guardada do relatório, responde 200 com ela, `stale: true`, `stale_message` explicando o porquê e `stale_code` (`wcl_unavailable` se o Warcraft Logs está fora do ar ou limitando, `unexpected_error` se o erro é do LogCoach; `null` na lista normal) (`fetched_at` é a hora da lista guardada; a tela mostra "Mostrando a lista de HH:MM"); sem lista guardada, responde o erro (503 `wcl_unavailable` ou 500 `unexpected_error`). Só lutas de chefe e dificuldade suportados vêm como `in_progress`; pull de outro chefe já vem cinza com o motivo normal. Cada luta traz `unsupported_code` (`short`, `unsupported_boss`, `unsupported_difficulty`, `in_progress`, `upload_paused`; `null` se suportada), pelo qual a lógica decide, e `unsupported_reason`, o texto montado a partir dele. Cada luta traz também `in_progress` (true enquanto sobe para o Warcraft Logs, com `supported: false` e o motivo "A luta ainda está subindo para o Warcraft Logs. Ela fica disponível aqui assim que terminar.") |
| GET | `/reports/{code}/fights/{fight_id}/players` | — | Magos Arcanos da luta escolhida (RF04), com `actor_id`, nome, reino, spec e item level **dessa luta**. Só para luta suportada: mesmos erros do `POST /analyses` (`fight_not_found`, `fight_too_short`, `unsupported_fight`, `report_not_available`, `wcl_unavailable`, `unexpected_error`, `query_limit`) |
| POST | `/reports/{code}/fights/{fight_id}/prefetch` | opcional | Recebe `{"actor_id"}` e começa a baixar em segundo plano os eventos da luta do jogador (~19 pontos), para a análise não esperar por eles. Responde na hora 202 `{"status": "started" \| "running" \| "ready"}`. Cliente = conta logada, ou o IP sem login (atrás de proxy reverso é o IP do proxy, a menos que o uvicorn rode com `--proxy-headers`): no máximo uma pré-busca na fila por cliente (a nova tira a anterior que ainda não começou, se ninguém mais a pediu) e 10 pré-buscas novas a cada 10 min (`ready`/`running` não contam); teto do processo de 30 por hora (~570 pontos, pouco mais da metade dos 1000/h do Warcraft Logs). Passou de um dos dois: 429 `prefetch_limit`. IPv6 conta pela rede /64. Durante a pausa depois de uma falha do Warcraft Logs, responde 503 `wcl_unavailable` sem gastar o limite. Conta que já usou as análises do mês: 403 `plan_limit`. Mesmos erros da rota de Magos (inclusive 500 `unexpected_error` e `query_limit`), mais `no_arcane_mage`; durante a pausa depois de falha, o erro lembrado (503 ou 500). Também põe na fila própria a busca dos top 10 do bracket do jogador (item 12.13; teto de 2 brackets novos por hora no processo, somando pré-busca e análise; falha dessa parte só vai para o log). A tela só chama quando a pessoa clica no personagem (personagem marcado sozinho não pré-busca), espera ~1 s com a escolha parada e ignora os erros (a análise busca os eventos sozinha); depois de um erro passageiro, um novo clique tenta de novo |
| POST | `/analyses` | opcional | Roda a análise de uma luta. Com login, guarda no histórico e conta no limite de 5/mês (RF14) |
| GET | `/analyses/{id}` | opcional | Resultado de uma análise. Análise de uma conta só abre para o dono |

**Erros.** Toda resposta de erro vem como `{"detail": {"code": "...", "message": "..."}}`. O `code` é fixo (o frontend decide o que fazer por ele) e a `message` já é o texto do item 8.2, pronto para mostrar ao usuário. Códigos: `invalid_link`, `report_not_available`, `fight_not_found`, `fight_too_short`, `unsupported_fight`, `no_arcane_mage`, `plan_limit`, `analysis_not_available`, `wcl_unavailable`, `unexpected_error`, `prefetch_limit`, `query_limit`, `email_taken`, `invalid_credentials`, `wrong_password`, `login_required`, `invalid_token`, `analysis_not_found`.

**Análise sem conta (RF01).** O backend aceita a análise sem login, mas não a coloca em histórico nenhum. O limite de 1 análise de demonstração é controlado no navegador; controlar no servidor fica para a publicação (item 13).

**Report privado × WCL fora do ar.** `report_not_available` (404) é só report privado ou inexistente: a API respondeu 200 com erro de GraphQL no campo do report ("This report does not exist." ou "You do not have permission to view this report.") e `report: null`; código mal formado cai no mesmo caso. `wcl_unavailable` (503) é quando a culpa não é do report, e a mensagem diz a causa e o que fazer:

- limite de pedidos (429, também o 1015 do Cloudflare), com o tempo do `Retry-After` quando vem;
- Warcraft Logs fora do ar ou instável (5xx, 52x do Cloudflare, manutenção, "Internal server error" do GraphQL, página HTML no lugar do JSON);
- bloqueio do Cloudflare (403 em HTML);
- demora para responder (timeout) ou sem conexão;
- erro do Warcraft Logs que não reconhecemos ("tente de novo; se continuar, recarregue a página"), com o corpo no log para investigar.

Falha nossa no acesso ao Warcraft Logs não é `wcl_unavailable`: credenciais do servidor ausentes ou recusadas (`CONFIG_MESSAGE`) e consulta GraphQL com defeito (`QUERY_MESSAGE`) saem como 500 `unexpected_error`, com a mensagem específica, porque só somem quando alguém corrige o servidor. A mensagem e o código são escolhidos em `wcl/client.py` (`WclUnavailableError(detail, user_message, error_code)`); a fonte e a rota só repassam. Se a luta pedida não está na lista guardada e a busca nova falhou, a resposta é o erro do Warcraft Logs, não `fight_not_found`. Vale para todas as rotas que leem o Warcraft Logs. Nos dois casos o link de exemplo continua abrindo.

**Erro inesperado.** Exceção que nenhuma rota tratou (bug nosso) responde 500 `unexpected_error` ("Erro inesperado no LogCoach. O problema é nosso, não do seu relatório. Tente de novo; se continuar, recarregue a página."), e a causa vai só para o log. É um middleware em `app/main.py`, por dentro do CORS (para o navegador deixar a tela ler a resposta); os erros do `api_error` e os 422 de validação passam sem mudança. No frontend (`lib/api.js`), resposta sem `detail.code` (500 cru, 502/504 do proxy) vira `unexpected_error` com o mesmo texto, e 422 de validação vira `invalid_request`.

**Escolha do jogador.** A rota de jogadores da luta devolve cada Mago Arcano com o `actor_id` do Warcraft Logs (id do ator no report), e o `POST /analyses` recebe `{report_code, fight_id, actor_id}`. A rota procura esse id entre os Magos Arcanos da luta escolhida; id de outro personagem (outra spec, outra luta) ou que não existe dá `no_arcane_mage`. Homônimos de reinos diferentes têm ids diferentes, então não há ambiguidade. Nome + reino só é usado para os top 10, que o ranking traz sem id: a regra fica em `wcl/players.py` (`find_player`, com `normalize_server`: "Area 52" = "area-52" = "Area52").

**Lista leve e Magos por luta.** Ao colar o link vem só a lista de lutas de chefe: o log pode ter o dia inteiro do jogador (outras raides, masmorras), e baixar atores e `playerDetails` de tudo gasta pontos à toa. As lutas não suportadas aparecem em cinza; os Magos Arcanos só são buscados quando o usuário escolhe uma luta suportada, e os eventos assim que o jogador fica definido na tela (escolhido, único Arcano da luta ou personagem lembrado), pela pré-busca. Lista de Magos vazia não entra no cache: logo depois da luta o Warcraft Logs pode ainda não ter processado os dados de combate. O `POST /analyses` usa os mesmos caches: se a luta pedida não está na lista guardada (log ao vivo, pull novo), busca a lista uma vez antes de responder `fight_not_found`. Luta em andamento (`inProgress`) de chefe e dificuldade suportados vem com `in_progress: true` e não pode ser escolhida; a tela a mostra diferente das não suportadas (selo "Subindo…").

**Atualização automática.** Com o log ao vivo (há luta subindo, ou nesta sessão já apareceu luta nova, liberada ou subindo), a tela de escolher a luta refaz a lista sozinha a cada 4 min, contados do fim da última busca e só com a aba visível; ao voltar à aba depois desse tempo, atualiza na hora. Um pull dura 3–7 min, mais a conversa entre pulls, então atualizar antes disso não traz nada; quem quiser adiantar clica em "Atualizar lutas", que reinicia a contagem. Para depois de 3 atualizações seguidas sem novidade (~12 min); novidade (luta nova, liberada, começando ou terminando de subir) zera a contagem, e o clique religa. Relatório sem luta subindo nem novidade não liga sozinho. O aviso mostra o estado numa região `aria-live` (anunciada só quando muda) e a contagem em minutos fora dela.

**Pausa depois de falha.** Falha do Warcraft Logs (fora do ar, limite, rede ou erro nosso) fica lembrada por processo (`WclCooldown`): 8 s; 60 s no limite de pedidos sem `Retry-After`; ou o `Retry-After` do Warcraft Logs, até 5 min. Nesse tempo nenhuma consulta vai à API (lista, Magos, eventos, pré-busca): vem a lista guardada com `stale` ou o mesmo erro, e a mensagem do limite diz quanto falta. Luta fora da lista guardada responde com o mesmo status e código do erro da busca (503 `wcl_unavailable` ou 500 `unexpected_error`). Report privado não pausa nada.

**Log ao vivo e upload pausado.** `ReportResolved.live` é verdadeiro se o Warcraft Logs recebeu dados do log há no máximo 10 min (`endTime` do report, que vem de graça no `REPORT_FIGHTS`); com ele a tela liga a atualização automática mesmo colando o link entre pulls. A regra mede tempo **sem dados novos**, não a duração da luta: uma luta ou uma M+ em andamento manda dados o tempo todo. Luta de chefe e dificuldade suportados marcada como em andamento num log parado há mais de 10 min (uploader caiu, jogo fechou) vem com `upload_paused: true`, `in_progress: false`, `supported: false`, `unsupported_code: "upload_paused"` e o motivo "O envio deste log parou no Warcraft Logs (nada novo há mais de 10 min). Se o uploader voltar a enviar, clique em Atualizar lutas."; a tela mostra o selo "Upload pausado". Se a tela não está mais acompanhando o log (lista guardada ou automática parada), a luta subindo mostra "Sem atualização" em vez de "Subindo…". Ao abrir uma luta subindo ou pausada (`unsupported_code` `in_progress` ou `upload_paused`; a API decide pelo código, nunca pelo texto de `unsupported_reason`), a API busca a lista de novo uma vez antes de recusar com 422 `unsupported_fight`.

**Limite de consultas (`query_limit`, 429).** Cada cliente (conta logada, senão IP; IPv6 por /64) pode fazer 20 consultas que vão de fato ao Warcraft Logs a cada 30 min, somando `POST /reports/resolve`, a rota de Magos, a pré-busca (lista e Magos) e o `POST /analyses`; o que sai do cache e o relatório de exemplo não contam. Uma noite de raide ao vivo usa ~colar + 8 automáticas + ~10 lutas em 30 min; o limite segura um abuso em ~80 pontos/h por cliente, de 1000. Mensagem: "Você fez muitas consultas ao Warcraft Logs em pouco tempo. Para o LogCoach não estourar o limite de uso da API deles, cada pessoa pode fazer 20 a cada 30 minutos. Tente de novo em {N} min.". No resolve, com lista guardada, ela vem com `stale: true` e `stale_code: "query_limit"`.

**Links e erros do relatório.** Vale `warcraftlogs.com` com `www.`, sem subdomínio ou com subdomínio de idioma de 2 letras (`de.`, `ko.`…). Links do Classic (`classic.`, `sod.`, `fresh.`, `vanilla.`, `era.`) dão 422 `invalid_link` com "Esse link é do Warcraft Logs Classic. O LogCoach analisa só logs do World of Warcraft atual."; outro subdomínio, `invalid_link` com a mensagem de sempre. Relatório arquivado: 404 `report_not_available` com "Esse relatório foi arquivado no Warcraft Logs e não pode mais ser lido pela API. Peça para quem enviou reativá-lo ou use um log mais recente." (texto do WCL para arquivado ainda não observado). Luta que o WCL não acha na consulta dos Magos dá 404 `fight_not_found`, e jogador fora do report, 422 `no_arcane_mage`. No `POST /analyses`, o limite do plano é conferido antes de qualquer consulta.

**Login em rota pública.** Em rotas com login opcional, token inválido ou vencido vale como "sem login". Só as rotas que exigem login respondem `invalid_token`. Por isso o frontend confere a sessão salva com `GET /me` ao abrir o site e sai da conta se o token venceu; se uma análise feita com login volta com `saved: false`, ele também sai da conta.

**Limite do plano.** Conta por mês do calendário em UTC: as análises feitas desde o dia 1º às 00:00 UTC.

### De onde vêm os dados

As rotas não falam direto com o Warcraft Logs nem com o motor. Elas dependem de duas interfaces em `backend/app/services/sources.py`:

| Interface | O que faz | Implementação atual |
|---|---|---|
| `ReportSource.get_report(code, refresh=False)`, `get_fight_players(code, fight_id)`, `get_fight_data(code, fight_id, actor_id)` e `prefetch(code, fight_id, actor_id)` | Lutas do relatório; Magos Arcanos de uma luta; luta completa do jogador no formato do `fetch_fight` (12.8), que é o que o motor lê; pré-busca dessa luta em segundo plano | `WclReportSource` (`DATA_SOURCE=wcl`): lista com `REPORT_FIGHTS` (~1 ponto) e Magos com `FIGHT_PLAYERS` (~2 pontos por luta), com um `WclClient` por processo (`shared_client`). Cache na memória do processo (`ReportCache`) da lista por código (até 128) e dos Magos por (código, luta) (até 1024), por 6 h; lista de Magos vazia não é guardada. `refresh` menos de 8 s depois da última busca devolve o cache; com o WCL fora do ar e lista guardada, devolve a guardada com `stale`. Eventos no `FightDataStore`: até 8 lutas, por 6 h, por (código, luta, ator) (uma luta tem ~1,3 MB de JSON e ~4,5 MB na memória; o cache só cobre "escolher → analisar" e uma análise repetida), com single-flight: quem pede uma luta que está baixando espera a mesma busca (até 180 s); se a pré-busca ainda está na fila, `get_fight_data` busca na hora e a tarefa da fila é cancelada. Chaves `FightKey(code, fight_id, actor_id)`; cópias feitas fora do lock. No desligamento, `shutdown_prefetch` cancela a fila (`cancel_futures`) e as buscas que estavam nela saem do store (ninguém espera busca da fila; o próximo pedido busca de novo); só as que já baixavam (no máximo 2) terminam. `prefetch(code, fight_id, actor_id, client)` aplica a fila e os limites (`PrefetchLimiter`: 10 novas por cliente em 10 min e 30 por hora no processo; clientes na ordem da última pré-busca, até 10 mil, limpeza no máximo uma vez por minuto). Depois de uma falha, `WclCooldown` segura todas as consultas (ver 12.3). A pré-busca roda num `ThreadPoolExecutor` do processo com 2 threads (`prefetch_executor`/`shutdown_prefetch`), não no BackgroundTasks, para não ocupar as threads das rotas. Falhas e o plano B do exemplo não entram em cache nenhum. `SampleReportSource` (`DATA_SOURCE=exemplo`): lê `app/samples/report_<código>.json` (lutas, mais `players` por id da luta; só o Harmonist, ator 455, na luta 34); `refresh` devolve a mesma lista; `get_fight_data` lê `app/samples/fight_<código>_<luta>_<ator>.json.gz` (só luta 34 e ator 455; cópia byte a byte de `tests/fixtures/<bracket>/reference_harmonist.json.gz`, gravada pelo `save_fixtures.py` e conferida por teste, e empacotada no `package-data` para o plano B funcionar fora do repo) e `prefetch` responde `ready` |
| `Analyzer.analyze(report, fight, player)` | Devolve o resultado da análise | `SampleAnalyzer`: lê `app/samples/analysis_<código>_<luta>.json`. O motor vai ler os eventos com `source.get_fight_data(report.code, fight.id, player.actor_id)` (a fonte entra pelo construtor, em `get_analyzer`) e aproveita a pré-busca; enquanto for o `SampleAnalyzer`, o `/analyses` não baixa eventos |

Os arquivos de exemplo são marcados como exemplo (`"sample": true` e `"source": "exemplo"`) e a interface mostra um aviso amarelo. O `WclReportSource` já lê relatórios reais; o analisador ainda é o de exemplo, então só a luta de referência, e só para o Harmonist, tem resultado (outras lutas ou outros Magos dão `analysis_not_available`, sem gravar no histórico). O exemplo foi refeito em 28/10 a partir do log real (fixtures com buffs externos): só o impacto em % das regras e o tempo ativo são ilustrativos (ver `_nota` do arquivo). A soma dos `impact_pct` fecha com a diferença de DPS: o que as regras não explicam fica no erro `hipotese` (RF23), e `tests/test_samples.py` confere isso. Quando o motor ficar pronto, basta trocar o que `get_analyzer()` devolve. Nenhuma rota nem tela muda.

No `WclReportSource`: entram só Magos com spec Arcano **na luta escolhida**; spec e item level vêm da própria luta (`friendlySpecs` e `friendlyItemLevels`, na ordem de `friendlyPlayers`; se faltar a spec de algum Mago, completa com `playerDetails(fightIDs: [luta])`); chefe suportado = encontro com YAML em `encounters/`, dificuldade listada em `difficulties` do YAML (Nek'zali: só Mítico) e luta de 60 s ou mais; chefe e dificuldade em pt-BR (`pt_br.yaml`). Report privado ou inexistente vira `report_not_available`; o que é culpa do Warcraft Logs ou nossa vira `wcl_unavailable` (12.3). Nos dois casos o link de exemplo (`XhrmBaYkGCAQjH2D`) abre com os arquivos de `app/samples/` (plano B da demo), e essa resposta não entra no cache. Consulta conferida no report de referência.

**Nomes na resposta (RF25).** Em `POST /analyses` e `GET /analyses/{id}`, cada jogador comparado vem em `comparison.players` (hoje o top 10; o 11º do bracket quando o log analisado está no top 10 (RF21) e os colegas de raide entram com o motor) com `display_name` (pseudônimo estável: `top01`… pela posição no ranking, `raid_01`… pela ordem de ID; a tela mostra "Top 1", "Raide 1") e `name` (nome real, ou nulo quando não há). O jogador analisado vem com `display_name` = `name`. Quem decide o que mostrar é o frontend. A IA recebe só os pseudônimos: os nomes reais nunca entram no pacote da IA.

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
4. **Com quem comparar.** Os 10 melhores logs da mesma especialização, chefe e dificuldade **dentro da faixa de item level do jogador** (o "bracket" do Warcraft Logs, de 3 em 3 níveis: 326–328, 329–331…). Assim a diferença mostrada é de execução, não de equipamento. Se o jogador já estiver nesse top 10, o relatório reconhece e o log analisado sai da comparação e entra o 11º colocado do bracket (outro log do mesmo personagem no top 10 continua como um top qualquer) (item 12.13).
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
| Picos de dano e dano evitável | Picos com mecânicas, vida mínima, defensivo e cura; classe de cada mecânica em `mechanics` do `nekzali.yaml` |
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
| `client.py` | `WclClient` (`from_env()` lê as chaves do `Settings`, em `app/config.py`): troca `WCL_CLIENT_ID` + `WCL_CLIENT_SECRET` por um token (fluxo *client credentials*), guarda o token (vale ~360 dias) e renova sozinho 60 s antes de vencer ou quando a API recusa o token, sob lock (várias rotas ao mesmo tempo pedem um token só; quem espera na fila desiste em 10 s). O backend usa um cliente por processo (`shared_client()`; `close_shared_client()` fecha ao desligar o app); os scripts abrem o próprio. `query()` faz o POST GraphQL; `events()` segue a paginação (`nextPageTimestamp`). Tempos: conectar 5 s; ler 10 s nas consultas pequenas (lista de lutas, Magos, metadados: passou disso, o WCL travou e o usuário recebe o erro em vez de esperar sem retorno, limite de atenção de Nielsen); 60 s nas páginas de eventos e no `FIGHT_META` (`EVENTS_TIMEOUT`, busca pesada da pré-busca, em segundo plano); token 10 s. Erro de validação do GraphQL (campo, argumento ou variável) é bug nosso: `QUERY_MESSAGE`, com `error_code="unexpected_error"`, como o `CONFIG_MESSAGE`. Também decide de quem é cada erro: report privado ou inexistente vira `WclError`; o resto vira `WclUnavailableError(detail, user_message)`, com a mensagem pronta (`UNAVAILABLE_MESSAGE`, `TIMEOUT_MESSAGE`, `NETWORK_MESSAGE`, `BLOCKED_MESSAGE`, `CONFIG_MESSAGE`, `QUERY_MESSAGE`, `UNEXPECTED_MESSAGE`, `rate_limit_message()`). Observado na API real em 28/10/2026: erros de GraphQL vêm com HTTP 200 (até o de sintaxe); token inválido na API volta **404 em HTML**, não 401; credencial errada no `/oauth/token` volta 401 `invalid_client`; os cabeçalhos `x-ratelimit-*` medem pedidos (800 na API), não os 1000 pontos/hora do `rateLimitData`. No desligamento: `stop_shared_client()` (liga o `stop()` do cliente do processo, sem criar um; `events()` para antes da próxima página) → `shutdown_prefetch()` → `shutdown_tops()` → `close_shared_client()`. 404 em HTML repetido mesmo com o token novo é erro do WCL (`wcl_unavailable`), não configuração nossa. Na busca pesada (eventos), só limite de pedidos ou 5xx ligam a pausa (`WclCooldown`); timeout e rede não. |
| `queries.py` | Consultas GraphQL: lista de lutas de chefe do report (`REPORT_FIGHTS`, sem jogadores), Magos de uma luta (`FIGHT_PLAYERS`, com `friendlySpecs`/`friendlyItemLevels` e atores filtrados por `subType: "Mage"`; reserva `FIGHT_PLAYER_DETAILS`), dados da luta, brackets do encontro, rankings. |
| `fetch.py` | `fetch_report()` devolve só as lutas do report; `fetch_fight_players(client, code, fight_id)` devolve os jogadores da luta (id, spec, item level) e os Magos do report (nome, reino), os dois usados pelo `WclReportSource`; `fetch_fight(client, code, fight_id, actor_id=… ou name=…, server=…)` devolve uma luta pronta para o motor: o jogador analisado vem pelo id do ator, os top 10 por nome + reino; `fetch_rankings()` e `bracket_index()` acham os top N do bracket. O `FIGHT_META` usa `timeout=EVENTS_TIMEOUT`; report nulo vira `WclError`. O `FIGHT_PLAYERS` foi conferido na API real em 28/10/2026 (`tests/fixtures/fight_players_XhrmBaYkGCAQjH2D_34.json`, anonimizada): as três listas `friendly*` vêm do mesmo tamanho e na ordem de `friendlyPlayers`, com spec em texto e item level inteiro. |
| `tops.py` | `fetch_tops(client, encounter_id, class, spec, difficulty, bracket, n=10, spare=3)`: os n primeiros do ranking do bracket com a luta completa de cada um (`fetch_fight` por nome + reino) e a posição real no ranking (`rank`). Pede n + 3 do ranking: luta que não abre (personagem renomeado, report privado ou apagado) é pulada e entra o próximo (`skipped`); WCL fora do ar interrompe. `rankings` traz quem é cada posição lida (rank, report, luta, nome, reino), mesmo as que não abriram (RF21). Usado pela aplicação (`services/tops.py`, 12.13, com n = 11) e pelo `save_fixtures.py` (n = 10). Medido em 04/11: ~12 pontos por top, ~124 por 10 tops, ~155 s |
| `players.py` | `find_player()` acha o jogador nos atores do report pelo id ou por nome + reino (homônimos desempatados pelo reino; ambíguo ou inexistente dá `PlayerNotFoundError`, um `WclError`) e `normalize_server()`. |
| `anonymize.py` | Troca os nomes de jogadores por pseudônimos antes de salvar. |

**Limite da API:** 1000 pontos por hora. Lista de lutas ~1 ponto; Magos de uma luta ~2 (com `playerDetails` seriam ~3); a consulta antiga, com atores e `playerDetails` da noite inteira, custava ~3 e crescia com o tamanho do log. Uma luta completa custa ~19 pontos (eventos, `CombatantInfo`, as tabelas de casts e de dano num pedido só, `FIGHT_TABLES`, ~3 pontos (o `own`, por habilidade, custa 1), para o tempo ativo e o DPS oficial, a vida em cada golpe recebido e a cura recebida); o kill de referência + top 10 custa ~210 (medido em 03/11). Medido no report de referência; cada consulta custa no mínimo 1 ponto.

**Formato de uma luta** (`fetch_fight`). Os tempos ficam em **ms do report**, como vêm da API. A conversão para "segundos desde o início da fase" é do motor, usando `meta.fight.phaseTransitions`.

| Chave | Conteúdo |
|---|---|
| `meta` | Código do report, `fight` (id, encontro, dificuldade, kill, início/fim, `phaseTransitions`), `duration_ms` |
| `phases` | Nomes das fases do encontro (`id`, `name`, `isIntermission`) |
| `actors`, `abilities` | Só os que aparecem nos eventos desta luta |
| `player` | Ator do jogador + `details` (spec, `minItemLevel`/`maxItemLevel`; `potionUse` e `healthstoneUse` vêm sempre 0 e não são usados) + `combatant` (evento `CombatantInfo`: `stats` com intelecto, crítico, aceleração, maestria e versatilidade, e `auras` ativas no pull, sem gear nem talentos) + `active_time_ms` (`activeTime` da tabela de casts, o "Active Time" da página da luta) + `damage` (tabela `DamageDone`: `total`, `total_time_ms`, `dps` = total ÷ tempo, o mesmo número do ranking, e `rdps_taken`, o dano que o WCL credita a quem apoiou o jogador, como o Evocador Aumentação; `credited`, esse crédito por id de habilidade, da mesma tabela filtrada pelo jogador; nulo sem a linha do jogador). As duas tabelas vêm de `fetch_fight_tables` (`FIGHT_TABLES`, com aliases `casts`, `damage` e `own`, a de dano filtrada pelo jogador) |
| `events.casts` | Casts do jogador (`begincast` e `cast`) |
| `events.buffs` | Buffs no jogador, com stacks (`applybuffstack`/`removebuffstack` trazem `stack`). Filtro `sourceID` do jogador: no WCL o "source" do filtro de buffs é o dono da aura, então vêm também os externos (PI, lust) |
| `events.damage_done` | Dano do jogador (sem a lista de buffs por golpe, que já está em `buffs`) |
| `events.damage_taken` | Dano recebido pelo jogador (filtro `sourceID`, mesma convenção dos buffs; atacante em `sourceID`, jogador em `targetID`), com `includeResources`: vida do jogador depois do golpe (`hitPoints`, `maxHitPoints`). Dos recursos ficam só esses dois (`TAKEN_FIELDS`) |
| `events.healing_taken` | Cura recebida pelo jogador (filtro `targetID`: na cura o filtro funciona do jeito comum, conferido em 03/11) |
| `events.deaths` | Mortes da raide inteira: o WCL ignora `targetID` e `sourceID` em `Deaths` (conferido em 03/11); o motor separa as do jogador |
| `events.boss_casts` | Casts dos inimigos (habilidades do chefe e dos adds do `nekzali.yaml`) |

**Fixtures.** `cd backend && python scripts/save_fixtures.py` baixa o kill de referência e os top 10 do mesmo bracket para `tests/fixtures/nekzali_mythic_<min>_<max>/` (`--only-reference` só a referência, `--force` para sobrescrever). Cada luta é um `.json.gz`; o `index.json` lista o bracket e o DPS/duração de cada top. Servem para os testes, para desenvolver sem internet e como plano B da demo. Os tops vão também, byte a byte, para `app/samples/tops/<bracket>/` (o `SampleTopsSource` lê de lá; conferido por teste).

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

## 12.10 Motor: Salvo, Arcane Soul e Prismatic Bolt

Regras do Arthur (28/10/2026), conferidas nas 11 fixtures. Código em `backend/app/engine/` (`rules.py` lê os YAML; `timeline.py` lê janelas e acúmulos de buffs; `prismatic_bolt.py` e `arcane_soul.py` fazem as contas). Regras em `arcane_mage.yaml` (`barrage`, `prismatic_bolt_rng`, `arcane_soul`, `surge_window`).

**Por que Barrage com 12 ou mais.** Pelo snowball de procs: todo hit de magia arcana (Missiles, Meteorite, o próprio Barrage) pode dar Clearcasting, e o Barrage derruba 1 Meteorite a cada 5 acúmulos de Salvo (15 → 3, 20 → 4, 25 → 5). Mais hits → mais Clearcasting → mais Missiles → mais Salvo. A chance de Prismatic Bolt tem os mesmos odds (linear, 2% por acúmulo): duas Salvas com 11 dão a mesma chance que uma com 22. O que tira Bolt é o Salvo estourar no cap, e isso aparece nos procs esperados por minuto (Salvo gasto por minuto), que o `prismatic_bolt.py` já calcula.

**Arcane Soul (Sunfury).** Começa quando o Surge acaba (~17,4 s). Dentro dele o Barrage não gasta Salvo (medido: 20 dos 21 Barrages sem consumo do Harmonist), então cada Barrage rola Seta e meteoros de graça. Regra: entrar com **20 de Salvo ou mais** (25 é o máximo, mas de 20 para 25 o ganho é ~0,3%, e às vezes vale soltar um Barrage para não estourar). A causa típica de entrar baixo é Barrage nos 2 últimos GCDs antes do Soul; Overpowered Missiles sobe o Salvo para 25 na hora. `soul_entries()` devolve, por entrada, o Salvo, se ficou abaixo do mínimo (`mistake`), se houve Barrage nos últimos GCDs e se houve Overpowered.

**Janela do Surge.** Não entrar de mão vazia (Salvo até 11 e no máximo 1 Clearcasting), senão o burst enche de Arcane Blast: nos tops, as 5 entradas assim deram 3 Blasts por janela. `surge_windows()` devolve, por janela, Salvo e Clearcasting no começo, os Blasts dentro e `empty_handed`. Fora o Surge de abertura, os tops soltam 0,5 Blast por janela. O Harmonist não entrou de mão vazia nenhuma vez e mesmo assim soltou 2,8 por janela: a causa está dentro da janela.

**2ª poção com o Surge ou no CD.** Nos 30 s depois de um Surge, o DPS médio é 37% maior que no meio do ciclo (307,7 mil × 225,0 mil; 24 e 20 janelas sem poção, Power Infusion nem lust, nas 11 fixtures). Como a poção multiplica o dano feito enquanto dura, ela rende ~37% mais junto com o Surge. Ganho de alinhar ≈ bônus de dano da poção × 2,6% do dano da luta. O Potencial da Luz dá +695 de intelecto; o Harmonist tinha 3.575 (`combatantInfo` do kill de referência), ou seja, ~+19% de dano enquanto a poção dura (supondo dano proporcional ao intelecto, sem buffs de raide). Alinhar a 2ª poção com o Surge rende ~0,48 milhão de dano a mais: **~+1,2 mil de DPS, ou ~0,5% do dano da luta**. Segurar a poção só não vale se a luta acabar antes do Surge.

**Prismatic Bolt: decisão × sorte.** A spec depende muito de RNG, e o relatório não pode cobrar azar como erro.

| Medida | Como é calculada | O que mostra |
|---|---|---|
| Esperado | Soma, em cada Barrage, de 2% × acúmulos de Salvo naquele instante | A **decisão** |
| Recebidos | Barrages seguidos de proc em até 0,5 s | O que aconteceu |
| Sorte (z) | (recebidos − esperado) ÷ √Σ p(1 − p) | O **RNG**: abaixo de −2 é azar, acima de +2 é sorte |

`bolt_procs(fight, soul=None|True|False)` faz a conta para a luta inteira, só dentro do Soul ou só fora.

**Validação.** Nos 1.015 Barrages das fixtures, a taxa de proc por faixa de Salvo bate com 2% por acúmulo (10–14: 26%; 15–19: 35%; 20–24: 45%; 25: 53%); o ajuste dá 2,1%. No kill de referência:

| | Harmonist | Tops (média) |
|---|---|---|
| Entradas no Soul com 20+ de Salvo | 2 de 5 (0, 20, 1, 18, 22) | 23 de 43 |
| Entradas com Barrage nos 2 últimos GCDs (sem Overpowered) | 1 de 5 | 6 de 43 |
| Arcane Blast por janela de Surge (fora a de abertura) | 2,8 | 0,5 |
| Procs de Seta: recebidos ÷ esperados na luta | 28 ÷ ~41 (z −2,8) | z +0,9 |
| Procs esperados por minuto no Soul (decisão) | 1,0 | 1,2 |

A falta de Seta do Harmonist é em parte decisão (entrar no Soul com pouco Salvo) e em grande parte azar. Um ranking de melhores logs tende a escolher lutas com sorte, e o relatório precisa dizer isso.

## 12.11 Motor: fases, referência dos tops e tabelas

Base do motor (passo 4, PR `feat/motor-base`). Tudo em `backend/app/engine/`, lendo a luta no formato de `wcl.fetch.fetch_fight` (tempos em ms do report).

| Módulo | O que faz |
|---|---|
| `fight.py` | Fases da luta a partir de `phaseTransitions` + nomes do WCL (`PhaseSpan`: id, nome em português, início, fim, intermissão). Uma fase que se repete vira dois trechos com o mesmo id; as tabelas somam os dois. Também: segundos desde o início da luta, dano com o absorvido, casts concluídos |
| `names.py` | Nome em português por ID (`pt_br.yaml`: magias, NPCs e fases); o que não estiver lá sai em inglês, como veio do WCL |
| `baseline.py` | Régua de cada métrica de desempenho a partir dos tops (decisão de 03/11): **atenção** = pior que 3 de cada 4 tops (quartil do lado ruim); **erro** = pior que o pior top. Com menos de 5 tops, usa os valores reserva do YAML. `text()` diz ao usuário de onde saiu a régua ("mediana dos 10 tops: 6%") |
| `abilities.py` | Tabela por habilidade e por fase (RF22): casts por minuto e % do dano, jogador × média dos tops que tiveram a fase. Cast e dano com IDs diferentes viram uma linha só (`ability_groups` em `arcane_mage.yaml`; ex.: Mísseis conjurado como 5143, dano como 7268). Linhas com menos de 1% do dano ficam fora |
| `targets.py` | Dano por alvo e por fase, em %: o chefe primeiro (`boss_npc_id` do encontro), depois os adds, agrupados pelo NPC. Bater em add não é erro; a tabela mostra onde o jogador concentrou o dano e serve à IA para apontar padding |

Cada luta vira um **perfil** (`ability_profile`, `target_profile`). É o perfil, e não os eventos, que se guarda dos tops no cache de 24 h. A tabela junta o perfil do jogador com os dos tops.

**Conferido no kill de referência:** a tabela por habilidade reproduz os números medidos em 28/10 (ex.: Fase 2, Mísseis 30,9% × 35,3% do dano dos tops; Seta 14,5% × 24,0%). Na intermissão, o dano vai para o Eco de Jawae (78% no Harmonist, 73% nos tops) e os Amani; o chefe não recebe dano.

## 12.12 Motor: regras, impacto e diferença para os tops

Escopo fechado com o Arthur em 03/11. `measures.py` lê a luta uma vez e devolve um `FightMeasures` (é isso que se guarda dos tops); `checks.py` transforma as medidas em regras (`Check`: status, valor do jogador, dos tops, de onde saiu a régua, `impact_pct` e os fatos para o texto e para a IA).

| Regra (`id`) | Régua | Impacto em % do dano do jogador |
|---|---|---|
| `surge_touch_combo`: Touch até 3,5 s depois do Surge | fixa (YAML) | dano médio de um Touch casado − o do Touch que ficou fora |
| `touch_uses`, `surge_uses`: usos × possíveis (no CD desde o pull) | atenção se perdeu mais usos que a mediana dos tops | usos a mais perdidos × dano de um Touch / dano a mais de uma janela de Surge |
| `touch_drift`: atraso médio do Touch | tops | — (o custo está nos usos) |
| `surge_hold`: Surge segurado | fixa: mais de 10 s é atenção; mais de 15 s sem poção, lust, PI ou fase é erro | — |
| `barrage_low_salvo`: % de Barrage com menos de 12 | tops | `null`: o custo é o snowball |
| `soul_entry`: entrada no Arcane Soul com menos de 12 | fixa: cada entrada é erro; 20+ é o ideal | Barrages no Soul × acúmulos a menos até 20 × (dano por Salvo + 2% × dano do Bolt) |
| `surge_empty_handed`: menos de 12 de Salvo e sem Clearcasting | fixa | `null` (já está no Blast) |
| `surge_blasts`: Blasts por janela de Surge | tops; com pouca Clearcasting recebida não passa de atenção | Blasts acima da mediana dos tops × (Missiles − Blast) |
| `prismatic_bolt`: procs esperados por minuto (decisão) | tops | `null`; o azar vai para a linha de sorte |
| `bolt_munch`: proc de Bolt perdido | tops | munch acima da mediana × dano do Bolt |
| `potion`: 1ª com o primeiro lust, 2ª com um Surge | fixa | poção a menos ou fora do Surge × bônus (19%) × DPS pós-Surge × 30 s |
| `active_time`: tempo ativo | tops (mediana) | mediana ÷ tempo do jogador − 1 |
| `damage_peaks`: picos de dano (defensivo e posicionamento) | fixa (veredito por pico) | `null` (risco) |
| `avoidable_damage`: dano evitável recebido, % da vida por minuto | tops (pior que o quartil / que o pior) | `null` (risco) |
| `power_infusion`, `deaths` | contexto / fixa | mortes: tempo morto |

**Diferença para os tops (`gap`).** Em % do dano do jogador: total = DPS médio dos tops ÷ DPS do jogador − 1; erros = soma dos impactos; sorte = (procs de Bolt esperados − recebidos) × dano médio do Bolt; não explicado = o resto (RF23). O DPS do jogador e dos tops é o do Warcraft Logs (`FightMeasures.dps` = `official_dps`, tabela `DamageDone`, igual ao do ranking; a soma dos eventos fica de reserva para luta sem o número); as proporções (impacto, sorte, tabelas por habilidade e alvo) continuam pela soma dos eventos, porque numerador e denominador saem dos mesmos eventos. No kill de referência (fixtures de 04/11): **18,0% = 6,6% de erros + 9,5% de sorte + 1,9% não explicado**. Até 03/11 o DPS era a soma dos eventos e dava 20,0% (3,9% não explicado): os eventos do Mago incluem o dano que o WCL credita ao Evocador Aumentação que o apoiou (Ebon Might, Prescience, Shifting Sands nas magias dele, mais Fate Mirror, Breath of Eons e Bombardments como se fossem habilidades dele), que no top03 é 11,2% do dano e no top09 5,0%. Essas três habilidades (`damage_credited_to_others` em `arcane_mage.yaml`) saem do dano do jogador em todo o motor (`engine/fight.damage_done`); `FightMeasures.support_pct` guarda o % creditado ao Evocador, como contexto de que o jogador teve apoio (o DPS oficial já desconta; no top04 e no top07 os 0,2% são só Bombardments, que já saem do dano do Mago). **DPS dos tops pelo ranking:** `measure(..., dps=entry.dps)` usa o DPS do ranking (`TopEntry.dps`, que nunca falta e é igual ao da tabela), para uma cópia antiga sem `player.damage` não misturar soma dos eventos com número do WCL na média (top03 pela soma levaria a diferença a 19,1%). Teste confere, nas 11 fixtures, que a soma bruta dos eventos = dano oficial + creditado. **Ganho do apoio descontado dos golpes com apoio (decisão do Arthur, 04/11, `engine/support.py`):** o Ebon Might, o Prescience e o Shifting Sands aumentam o dano das magias do próprio Mago, e o WCL credita esse ganho ao Evocador; os eventos não trazem a divisão. A tabela DamageDone filtrada pelo jogador traz o crédito por habilidade (`player.damage.credited`, por id dos eventos; linhas agrupadas como Touch e Prismatic Bolt vêm em `subentries`). `damage_done` tira esse crédito só dos golpes dados com algum desses buffs ativo (`support_buffs` no YAML; janelas por buff e por quem aplicou, unidas: com dois Evocadores, o fim do buff de um não fecha a janela do outro), na mesma fração dentro de cada habilidade; se o crédito passa do dano com apoio, ou não há golpe com apoio, sai de todos os golpes da habilidade por igual. Resultado: o dano do motor bate na unidade com o total oficial nas 11 fixtures, e o Touch do top03 (antes +46% pelos eventos) fica igual ao do WCL. A média dos Mísseis nos tops na Fase 2 passou de 35,4% para 35,5%; a diferença do Harmonist não muda (ele não teve apoio). Sem os números do WCL (luta antiga), só as três habilidades do Evocador saem.

**Tempo ativo.** Vem do Warcraft Logs (`player.active_time_ms`), dividido pela duração da luta menos o tempo morto e as fases sem alvo. Nas fixtures: Harmonist 98,6%, tops de 99,2% a 99,8% (impacto ~1,0%). Até 03/11 era uma conta própria (cast com tempo de conjuração do início ao fim, instantâneo um GCD, Missiles até o último tick, 0,3 s de latência) que dava Harmonist 93,8% e tops 96,6% a 98,5%, quase triplicando a diferença; ela fica de reserva. **Uma régua só para todos:** a comparação usa a do WCL só se o jogador e todos os tops a têm; se faltar em alguma luta (cache ou cópia antiga), todos usam a conta própria, porque as duas réguas diferem de 3 a 5 pontos. Com fase sem alvo (`downtime_excluded_phases`) na luta, o número do WCL é recusado (ele conta o que foi conjurado nela). **Erro só a partir de 2 pontos abaixo do pior top** (`active_time_error_margin_pts`, decisão do Arthur em 03/11: quem se afasta para fazer uma mecânica perde tempo ativo ajudando a raide); atenção continua sendo pior que o quartil de baixo. O Harmonist (98,6% contra o pior top 99,2%) fica em atenção. Reserva com menos de 5 tops: 99,3% atenção / 97,2% erro na régua do WCL e 98% / 96% na conta própria.

**Buffs ativos no pull.** Poção tomada antes do pull, Prismatic Barrier e Mirror Image não têm `applybuff` na luta: o primeiro evento é a saída. A linha do tempo (`engine/timeline.py`, `initial_stacks`) começa com o estado do pull: primeiro evento `applybuff` = inativo; primeiro `removebuffstack` para N = havia N + 1 (as cargas caem de uma em uma); senão a aura do `CombatantInfo`, quando ela lista o buff; sem ela, primeiro `applybuffstack` para N = estimativa de N − 1 (o Salvo sobe até 9 de uma vez) e `removebuff` ou `refreshbuff` sem entrada = ativo desde o pull. As auras vêm incompletas (nas fixtures de 03/11 faltam Barrier, Mirror Image e a poção do top09, que saem da inferência): aura ausente não quer dizer buff inativo. O Salvo listado nas auras zera no início do encontro (`removebuff` a 0,03 s, sem Barrage). O ganho do pull não conta em `stack_gains`. **Poção antes do pull** conta como uso (hora estimada pela saída do buff, ex.: top09 aos −2 s). O bônus de dano da poção é +695 de intelecto ÷ intelecto do jogador no pull (`CombatantInfo`, descontando a poção se ele entrou com ela); a reserva de 19% vale sem o atributo.

**Picos de dano (`engine/defensives.py`, decisão de 03/11).** Em vez de procurar combinações fixas de mecânicas, o motor acha os picos no log e explica cada um. **Candidato** = início de uma janela de 4 s com 60% da vida máxima de dano (depois da mitigação, contando o que escudos absorveram) **ou** o primeiro golpe dos 4 s que levaram a vida abaixo de 35%. Candidatos a até 9 s (janela + cura depois) do **primeiro** do grupo são o mesmo incidente; contar a partir do último encadeava dano contínuo em grupos de quase um minuto e escondia quedas (revisão de 03/11: no top06, vida a 17% saía como "ok"). Em cada incidente, se a vida caiu abaixo de 50% o pico mostra os 4 s que levaram à vida mínima; senão, a janela com mais dano. Janelas que começam antes do fim do pico anterior são o mesmo incidente e fica a de vida mais baixa. **Vida:** `hitPoints` do último golpe mais a cura recebida desde então (só eventos `heal`: escudo absorvido já sai do dano), até a vida máxima daquele momento (`maxHitPoints` muda com buffs de vida). Para cada pico: as mecânicas com a % do dano e a classe do YAML, a vida mínima, o defensivo **ativo no instante da vida mínima** (usado depois disso aparece como tardio: "uso de Barreira Prismática só depois da queda"), os defensivos disponíveis nesse instante (recarga em `defensives` do YAML da spec; Barreira Prismática é de todo Arcano, os outros só contam se o jogador os usou na luta; usado antes do pull conta a recarga desde o começo), a cura recebida até 5 s depois e o tempo com a vida abaixo de 35%. **Veredito:** `evitavel` (mais da metade do dano é de mecânica evitável), `defensivo` (vida abaixo de 50%, nenhum defensivo ativo e um disponível), `cura` (vida abaixo de 35% por mais de 3 s com menos de 20% da vida em cura: o problema não é do Mago) ou `ok` (coberto, ou a cura segurou). Limites em `peaks` do YAML do encontro. A regra `damage_peaks` lista os picos que não são `ok`, em pt-BR, para a tela e para a IA explicar; é risco, sem `impact_pct`.

**Classe das mecânicas (Nek'zali).** `avoidable`: Latent Cultist (poça do Essence Rend), Anguished Echoes (impacto no Soulcoil Ignition), corpo a corpo; `targeted`: Essence Rend; `assigned`: Hungering Pyre (soak) e Vessel of Awakening; `raid`: Soulcoil Rite, Corpse Blight, Grasping Depths, Possession Barrage, Uncoiling, Slithering Flame, Cremation. Fontes: guias Mythic Trap e WowCarry (o que está no Heroico vale no Mítico) e as fixtures (dano por minuto: as evitáveis ficam perto de zero nos tops; Latent Cultist: Harmonist 175 mil/min, mediana dos tops 18 mil). A regra `avoidable_damage` compara o dano evitável em % da vida por minuto vivo com os tops (Harmonist 25,9%, tops de 0 a 15,2%, mediana 4,7%: erro), com piso: atenção só acima de 1% e erro só acima da reserva de atenção (6%), para um pouco de dano não virar erro quando os tops tomam zero.

**No kill de referência:** 8 picos no Harmonist. Às 5:06, vida a 44% com 75% do dano da poça (evitável; a Barreira veio só depois da queda); às 6:39, Possession Barrage + Grasping Depths + Soulcoil Rite com a vida a 44% e a Barreira disponível (defensivo cabia); nos outros 6 a cura segurou (vida mínima de 54% a 76%). Nos tops: 7,9 picos por luta, 1,6 com defensivo cabível; nenhum pico com "faltou cura" nas 11 lutas. A lista `overlaps` do YAML ficou só descritiva.

**Clearcasting.** Não há chance fixa por hit (a maior parte vem do Barrage e do Missiles, que dependem da rotação). Levantamento de 03/11: 14,8 a 17,4 ganhos por minuto nas 11 fixtures. A "sorte de Clearcasting" usa a régua dos tops sobre os ganhos por minuto.

**Dano recebido.** Até 03/11 a busca pedia `DamageTaken` com `targetID` do jogador e vinha só o dano que ele causou nele mesmo: no WCL, o "source" desse filtro é quem recebe o dano. Corrigido em `wcl/fetch.py` e fixtures baixadas de novo em 03/11 (Harmonist: 1.364 golpes recebidos, antes 533).

## 12.13 Busca dos tops (cache de 24 h, RF21)

Código em `backend/app/services/tops.py` (passo 4.2). Entrega ao motor (`EngineAnalyzer`, passo 4.3) os tops com quem comparar o jogador; as rotas só disparam a pré-busca.

| Peça | O que faz |
|---|---|
| `TopsSource.get_tops(encounter_id, difficulty, item_level, own)` | `own` é o log analisado (`OwnLog`: report, luta, nome). Devolve um `TopsComparison`: `label` ("Top 10 do bracket 326–328"), `bracket` (faixa do jogador), `player_in_top` (RF21), `entries` (`TopEntry`, até 10, em ordem de rank, sem o log analisado), `stale` e `sample`. Cada `TopEntry` traz o que a tela mostra (`compared()` → `ComparedPlayer`: posição real no ranking, `display_name` `top01`… pela posição, nome real, reino, item level, DPS do ranking) e a luta comprimida (`fight_gz`, ~130 KB); `fight()` descomprime uma de cada vez (~4,5 MB na memória), no formato de `fetch_fight` |
| RF21 (decisão de 04/11) | A comparação é sempre com o top 10 do bracket. O snapshot guarda 11 tops; se o **log analisado** (mesmo report, luta e nome, sem diferenciar maiúsculas) está entre as 10 primeiras posições do ranking (`rankings`, mesmo que a luta dele não tenha aberto), `player_in_top` é verdadeiro e ele sai da lista: entra o 11º. Outro log do mesmo personagem (outro dia, outro grupo) é um top como qualquer outro; um colega de raide da mesma luta também não é o jogador (o nome separa) |
| `TopsSource.prefetch_tops(...)` | Chamado pela rota `/prefetch` (12.3): põe o mesmo `get_tops` numa fila de 1 thread (`tops_executor`; pedido igual já na fila não entra de novo) e volta na hora |
| `WclTopsSource` (`DATA_SOURCE=wcl`) | Bracket do jogador por `bracket_index` com os brackets do encontro (memória → banco, 24 h → WCL, 1 ponto; com o WCL fora do ar, os do banco mesmo vencidos). Item level fora dos brackets: `TopsNotAvailableError`. Snapshot por `TopsKey(encontro, dificuldade, bracket)` |
| Camadas | Memória (`tops_store`, um `FightDataStore` com single-flight: quem pede um bracket que está baixando espera a mesma busca, até 300 s; 1 h, até 16 snapshots) → banco (`TopsSnapshot` + `TopsLog`, 24 h, RNF03: um reinício do Cloud Run não gasta os pontos de novo) → WCL (`fetch_tops`, 12.8). A memória vale só 1 h para um snapshot lido do banco perto de vencer não ficar mais 24 h nela (no máximo ~25 h). Gravar troca o snapshot da chave numa transação; falha do banco só vai para o log |
| Custo e teto | Medido em 04/11 na API real: ~124 pontos para 10 tops e **~150 pontos e ~53 s para os 11** do código atual (o tempo varia muito com o WCL: 155 s numa medição anterior); um processo novo lendo do banco gasta só o que faltar dos brackets. `TOPS_FILL_LIMIT`: 2 brackets novos por hora no processo, **somando pré-busca e análise**. Acima dele, a pré-busca para sem buscar (`PrefetchLimitError`, só no log) e a análise usa a cópia vencida do banco, o exemplo ou dá `wcl_unavailable` com `TOPS_LIMIT_MESSAGE`. Orçamento: 30 pré-buscas de luta × ~19 + 2 × ~161 ≈ 890 dos 1000 pontos/hora. Conferido na API real (04/11): processo novo lendo do banco em 0,4 s sem gastar pontos; RF21 com o log real do top02 (sai, entra o 11º) e com um colega de raide da mesma luta (comparação normal) |
| Falhas | Respeita a pausa do processo (`WclCooldown`); limite de pedidos e 5xx ligam a pausa (`_heavy_fetch_pauses`). Uma busca de bracket que falhou (inclusive timeout e rede, que não ligam a pausa) fica lembrada por 5 min (`tops_failures`): cada tentativa pode gastar dezenas de pontos antes de falhar. Com o WCL fora do ar: snapshot vencido do banco com `stale` (não vai para a memória) ou, no bracket do kill de referência, a cópia do exemplo (`sample`); fora disso, `SourceUnavailableError`. Ranking vazio ou recusado (encontro sem ranking): `TopsNotAvailableError` (um `AnalysisNotAvailableError`). Menos de 5 tops é guardado assim mesmo (as réguas caem na reserva do YAML, `engine/baseline.py`) |
| `SampleTopsSource` (`DATA_SOURCE=exemplo`) | Lê `app/samples/tops/nekzali_mythic_326_328/` (cópia byte a byte das fixtures, anonimizada: nome nulo; o `fill_real_names` põe o real a partir do `names.local.json`). Outro encontro, dificuldade ou faixa: `TopsNotAvailableError`. `prefetch_tops` não faz nada. Limitação aceita: as cópias não guardam report nem nome, então não reconhecem o log analisado (no modo exemplo é sempre o do Harmonist, fora do top 10; no plano B do WCL fora do ar, um top desse bracket analisando o próprio log seria comparado com ele mesmo). Um identificador desses logs no repositório público permitiria descobrir os nomes pela API |

**Tabelas.** `TopsSnapshot` (`key` "3470:5:19", `fetched_at` em segundos desde 1970, `info` com `rankings`; a chave "brackets:3470" guarda os brackets do encontro, sem tops) e `TopsLog` (`key`, `rank`, `meta` com nome real, reino, item level, DPS, duração, report e luta, e `fight_gz`). Criadas na subida, como as outras. Nomes reais só no banco, na memória e na resposta (RF25, ocultos por padrão na tela); nunca nos arquivos versionados nem na IA.

**`FightOption`** ganhou `encounter_id` e `difficulty_id` (ids do WCL), que a pré-busca usa para achar o ranking; numa lista guardada antes deles, vêm nulos e a pré-busca dos tops não roda (a análise busca depois).

**DPS dos tops × do motor (revisão de 04/11).** O DPS do ranking bate com a soma dos eventos em 7 dos 10 tops e no Harmonist, mas o top03 (+11,2%) e o top09 (+5,0%) somam dano que o WCL credita ao Evocador Aumentação que os apoiou (Ebon Might, Prescience, Shifting Sands, Fate Mirror, Breath of Eons: `totalRDPSTaken` da tabela `DamageDone`), e o top04 e o top07 (+0,2%) o dano de Bombardments. Pelo ranking, a diferença do Harmonist para os tops é 18,0%; pelos eventos, 19,95%. Desde 04/11 o DPS vem do WCL (item 12.12, "Diferença para os tops").
