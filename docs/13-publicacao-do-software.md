---
description: Link de acesso à versão publicada.
---

# 13. Publicação do Software

> Entrega da banca final.

| Item                    | Plano                                            |
| ----------------------- | ------------------------------------------------ |
| Frontend                | Firebase Hosting ou Cloud Storage (Google Cloud) |
| Backend                 | Cloud Run (container)                            |
| Banco                   | Cloud SQL (PostgreSQL)                           |
| IA                      | Vertex AI (Gemini)                               |
| Custos                  | Créditos do Google Cloud do grupo                |
| URL pública             | _a adicionar_                                    |
| Plano B na apresentação | Rodar local com `DATA_SOURCE=exemplo`: o motor real roda sobre o kill de referência e os 10 tops guardados em `backend/app/samples/`, sem internet |

## Cuidados do deploy no Cloud Run

Levantados na revisão da área do Warcraft Logs (02/11/2026). **Ainda não feito.**

| Configuração | Por quê |
|---|---|
| CPU sempre alocada | A pré-busca dos eventos roda depois da resposta 202; com CPU só durante a requisição, ela para no meio |
| Uma instância só na alfa (`max-instances=1`) | Caches, limites de consulta, busca única por luta e pausa do Warcraft Logs ficam na memória do processo; com várias instâncias cada uma teria os seus |
| uvicorn com `--proxy-headers --forwarded-allow-ips='*'` | Sem isso, todo visitante sem login aparece com o IP do Google e todos dividem o mesmo limite |

## Passo a passo do deploy

_A documentar quando o primeiro deploy for feito._
