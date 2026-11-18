---
description: Link de acesso à versão publicada.
---

# 13. Publicação do Software

<table data-search="false"><thead><tr><th width="243.88330078125">Item</th><th width="485.083251953125">Plano</th></tr></thead><tbody><tr><td>Frontend</td><td>Firebase Hosting ou Cloud Storage (Google Cloud)</td></tr><tr><td>Backend</td><td>Cloud Run (container)</td></tr><tr><td>Banco</td><td>Cloud SQL (PostgreSQL)</td></tr><tr><td>Custos</td><td>Créditos do Google Cloud do grupo</td></tr><tr><td>URL pública</td><td><a href="https://logcoach.vercel.app/">https://logcoach.vercel.app/</a></td></tr><tr><td>Plano B na apresentação</td><td>Rodar local com <code>DATA_SOURCE=exemplo</code>: o motor real roda sobre o kill de referência e os 10 tops guardados em <code>backend/app/samples/</code>, sem internet</td></tr></tbody></table>

## Cuidados do deploy no Cloud Run

Levantados na revisão da área do Warcraft Logs (02/11/2026). **Ainda não feito.**

<table><thead><tr><th width="287.433349609375">Configuração</th><th width="446">Por quê</th></tr></thead><tbody><tr><td>CPU sempre alocada</td><td>A pré-busca dos eventos roda depois da resposta 202; com CPU só durante a requisição, ela para no meio</td></tr><tr><td>Uma instância só na alfa (<code>max-instances=1</code>)</td><td>Caches, limites de consulta, busca única por luta e pausa do Warcraft Logs ficam na memória do processo; com várias instâncias cada uma teria os seus</td></tr><tr><td>uvicorn com <code>--proxy-headers --forwarded-allow-ips='*'</code></td><td>Sem isso, todo visitante sem login aparece com o IP do Google e todos dividem o mesmo limite</td></tr></tbody></table>

## Passo a passo do deploy

_A documentar quando o primeiro deploy for feito._
