---
description: Link de acesso à versão publicada.
---

# 13. Publicação do Software

<table data-search="false"><thead><tr><th width="243.88330078125">Item</th><th width="485.083251953125">Plano</th></tr></thead><tbody><tr><td>Frontend</td><td>Vercel</td></tr><tr><td>Backend</td><td>Railway (container do <code>backend/Dockerfile</code>; serve também no Cloud Run)</td></tr><tr><td>Banco</td><td>PostgreSQL da Railway</td></tr><tr><td>Custos</td><td>Créditos do Google Cloud do grupo</td></tr><tr><td>URL pública</td><td><a href="https://logcoach.vercel.app/">https://logcoach.vercel.app/</a></td></tr><tr><td>Plano B na apresentação</td><td>Rodar local com <code>DATA_SOURCE=exemplo</code>: o motor real roda sobre o kill de referência e os 10 tops guardados em <code>backend/app/samples/</code>, sem internet</td></tr></tbody></table>

## Cuidados do deploy (Cloud Run ou Railway)

Levantados na revisão da área do Warcraft Logs (02/11/2026). **Ainda não feito.**

<table><thead><tr><th width="287.433349609375">Configuração</th><th width="446">Por quê</th></tr></thead><tbody><tr><td>CPU sempre alocada</td><td>A pré-busca dos eventos roda depois da resposta 202; com CPU só durante a requisição, ela para no meio</td></tr><tr><td>Uma instância só na alfa (<code>max-instances=1</code>)</td><td>Caches, limites de consulta, busca única por luta e pausa do Warcraft Logs ficam na memória do processo; com várias instâncias cada uma teria os seus</td></tr><tr><td>uvicorn com <code>--proxy-headers --forwarded-allow-ips='*'</code></td><td>Sem isso, todo visitante sem login aparece com o IP do Google e todos dividem o mesmo limite</td></tr></tbody></table>

## Passo a passo do deploy

Frontend na Vercel e backend na Railway, a partir do repositório no GitHub. O backend sobe pelo `backend/Dockerfile`, que serve também para o Cloud Run.

**Backend (Railway)**

1. New Project → Deploy from GitHub repo → `LogCoach`.
2. No serviço, Settings → Source → **Root Directory = `backend`**. Sem isso a Railway lê a raiz do monorepo, não acha app nenhum e o build falha ("Railpack failed to prepare the build"). Com a pasta certa, ela acha o `Dockerfile` e usa ele; build e start command ficam vazios.
3. Settings → Deploy → Replicas = 1 (caches e limites ficam na memória do processo, ver a tabela acima). A Railway não desliga a CPU entre requisições, então a pré-busca roda até o fim.
4. No projeto, + New → Database → PostgreSQL. Sem ele o SQLite fica dentro do container e as contas somem a cada deploy.
5. Variables do serviço do backend:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (referência ao banco; o driver psycopg é posto sozinho) |
| `APP_ENV` | `prod` |
| `JWT_SECRET` | gerado com `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `WCL_CLIENT_ID`, `WCL_CLIENT_SECRET` | as credenciais do Warcraft Logs (sem elas o app roda no modo exemplo) |
| `CORS_ORIGINS` | `["https://logcoach.vercel.app"]` (JSON; uma entrada por domínio do frontend) |

`PORT` vem da Railway; não definir.

6. Settings → Networking → **Generate Domain**. Conferir em `https://<domínio>/health` (`{"status":"ok"}`).

**Frontend (Vercel)**

1. Root Directory = `frontend` (framework Vite).
2. Environment Variables: `VITE_API_URL = https://<domínio da Railway>` (sem barra no fim). O Vite grava a variável no build, então é preciso fazer **Redeploy** depois de criar ou mudar.
3. Se o domínio da Vercel mudar, atualizar o `CORS_ORIGINS` do backend.
