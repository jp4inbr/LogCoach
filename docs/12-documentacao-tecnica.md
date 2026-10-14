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

## 12.4 Regras do Mago Arcano (em linguagem simples)

Cada regra compara o jogador com a média dos melhores no mesmo chefe:

| Regra | O que mede |
|---|---|
| Tempo parado | % da luta sem lançar magia |
| Uso de cooldowns | Quantas vezes cada cooldown foi usado vs. o máximo possível |
| Alinhamento de cooldowns | Se os cooldowns foram usados nas janelas de dano |
| Defensivos | Se defensivos foram usados nos momentos de dano alto |
| Mortes | Momento e causa das mortes |

> Feitiços e janelas exatos de cada regra: definidos pelo Arthur em `backend/app/rules/`.
