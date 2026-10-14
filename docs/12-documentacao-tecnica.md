# 12. Documentação de Desenvolvimento (Técnica)

> Em construção junto com o código.

## 12.1 Como rodar localmente

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # preencher as chaves
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## 12.2 Variáveis de ambiente

| Variável | Para quê |
|---|---|
| `WCL_CLIENT_ID` / `WCL_CLIENT_SECRET` | Acesso à API do Warcraft Logs |
| `GOOGLE_CLOUD_PROJECT` | Projeto do Google Cloud (Vertex AI) |
| `DATABASE_URL` | Banco (SQLite em dev, PostgreSQL em produção) |
| `JWT_SECRET` | Assinatura do login |

## 12.3 Endpoints da API (previstos)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/register` | Cadastro |
| POST | `/auth/login` | Login |
| POST | `/reports/resolve` | Recebe o link e devolve as lutas e personagens |
| POST | `/analyses` | Roda a análise de uma luta |
| GET | `/analyses/{id}` | Resultado de uma análise |
| GET | `/me/analyses` | Histórico do usuário |

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
4. **Comparação por fase.** Como cada luta tem duração diferente, o sistema compara "X segundos após o início da fase" do jogador com o mesmo ponto nos melhores logs, e não o tempo absoluto.
5. **Saída.** Um JSON de fatos (ex.: "CD principal usado 2 de 4 vezes possíveis; 1 fora de janela de burst na fase 2") vai para a IA, junto com as perguntas da camada 3.

## 12.6 Formato dos arquivos de regras (rascunho)

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
