---
description: Link de acesso à versão publicada.
---

# 13. Publicação do Software

<table data-search="false"><thead><tr><th width="243.88330078125">Item</th><th width="485.083251953125">Plano</th></tr></thead><tbody><tr><td>Frontend</td><td>Firebase Hosting ou Cloud Storage (Google Cloud)</td></tr><tr><td>Backend</td><td>Cloud Run (container)</td></tr><tr><td>Banco</td><td>Cloud SQL (PostgreSQL)</td></tr><tr><td>Custos</td><td>Créditos do Google Cloud do grupo</td></tr><tr><td>URL pública</td><td><a href="https://logcoach.vercel.app/">https://logcoach.vercel.app/</a></td></tr><tr><td>Plano B na apresentação</td><td>Rodar local com <code>DATA_SOURCE=exemplo</code>: o motor real roda sobre o kill de referência e os 10 tops guardados em <code>backend/app/samples/</code>, sem internet</td></tr></tbody></table>

## Cuidados do deploy no Cloud Run

Levantados na revisão da área do Warcraft Logs (02/11/2026). **Ainda não feito.**

<table><thead><tr><th width="287.433349609375">Configuração</th><th width="446">Por quê</th></tr></thead><tbody><tr><td>CPU sempre alocada</td><td>A pré-busca dos eventos roda depois da resposta 202; com CPU só durante a requisição, ela para no meio</td></tr><tr><td>Uma instância só na alfa (<code>max-instances=1</code>)</td><td>Caches, limites de consulta, busca única por luta e pausa do Warcraft Logs ficam na memória do processo; com várias instâncias cada uma teria os seus</td></tr><tr><td>uvicorn com <code>--proxy-headers --forwarded-allow-ips='*'</code></td><td>Sem isso, todo visitante sem login aparece com o IP do Google e todos dividem o mesmo limite</td></tr></tbody></table>

## Passo a passo do deploy

Alfa na web: frontend na Vercel e backend com PostgreSQL na Railway (o Cloud Run segue como plano de produção; o mesmo `backend/Dockerfile` serve nos dois).

### Backend na Railway

1. Em railway.com, **New Project → Deploy from GitHub repo** e escolha o LogCoach.
2. No serviço, **Settings → Root Directory = `backend`**. A Railway usa o `Dockerfile` e o `railway.toml` (healthcheck em `/health`, uma réplica).
3. **+ New → Database → PostgreSQL**.
4. Em **Variables** do serviço do backend:
   * `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (o código troca `postgresql://` por `postgresql+psycopg://`)
   * `APP_ENV` = `prod`
   * `JWT_SECRET` = valor gerado com `python -c "import secrets; print(secrets.token_urlsafe(32))"` (nunca no git)
   * `WCL_CLIENT_ID` e `WCL_CLIENT_SECRET` = cliente criado em warcraftlogs.com/api/clients (confidencial)
   * `PORT` = `8000`
   * `CORS_ORIGINS` = `["https://logcoach.vercel.app"]` (JSON, a URL do frontend)
5. **Settings → Networking → Generate Domain**, com a porta `8000`.
6. Teste `https://<dominio>/health`.

### Frontend na Vercel

1. **Settings → General → Root Directory = `frontend`** (lê o `frontend/vercel.json`, framework Vite).
2. **Settings → Environment Variables**: `VITE_API_URL` = URL do backend na Railway, sem barra no final.
3. Faça **Redeploy**: a variável é embutida no build.
4. Os previews por PR têm outra URL e só passam no CORS se forem incluídos em `CORS_ORIGINS`; a demo usa a URL de produção.

### Problemas comuns

* "Railpack failed to prepare the build": o Root Directory não é `backend` ou o `Dockerfile` não está na branch monitorada.
* 502 depois de gerar o domínio: a porta do Networking difere da que o uvicorn escuta (confira nos Deploy Logs).
* Erro de CORS no navegador: `CORS_ORIGINS` sem a URL exata do frontend.
