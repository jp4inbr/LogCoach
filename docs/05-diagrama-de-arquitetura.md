---
description: Como frontend, backend e banco de dados se conectam.
---

# 5. Diagrama de Arquitetura

```mermaid
flowchart LR
    U[Jogador<br/>navegador] --> FE[Frontend<br/>React + Vite]
    FE -->|HTTPS / JSON| API[Rotas FastAPI<br/>/reports, /prefetch, /analyses]

    subgraph BE[Backend - FastAPI Python]
        API --> RS[ReportSource<br/>services/sources.py]
        API --> TS[TopsSource<br/>services/tops.py<br/>cache memória + banco 24 h, RF21]
        API --> AN[EngineAnalyzer<br/>services/analyzer.py]
        RS --> CL[Cliente do WCL<br/>backend/app/wcl/<br/>um por processo, cache, limites,<br/>pré-busca dos eventos e dos tops]
        TS --> CL
        AN --> M
        subgraph M[Motor - engine/]
            M1[Medidas da luta<br/>measures.py] --> M2[Regras com limites<br/>tirados dos tops<br/>checks.py + YAML]
            M1 --> M3[Tabelas por habilidade<br/>e por alvo]
            M2 --> M4[Diferença para os tops<br/>erros + sorte + não explicado]
            M3 --> M5[report.py<br/>monta o AnalysisResult]
            M4 --> M5
        end
    end

    RS -. modo exemplo .-> SM[app/samples/<br/>kill de referência + tops]
    TS -. modo exemplo .-> SM
    CL -->|GraphQL + OAuth| WCL[API Warcraft Logs v2]
    API --> DB[(Banco<br/>SQLite em dev / PostgreSQL)]
    M5 -->|resultado salvo| DB
```

> As linhas tracejadas são o modo exemplo (sem internet).

## Como uma análise funciona

1. O jogador cola o link. O frontend valida o formato e o backend busca só a lista de lutas no Warcraft Logs (`/reports/resolve`).
2. Ao escolher a luta, o backend traz os Magos Arcanos dela. Quando o personagem fica definido, a **pré-busca** (`/prefetch`) baixa em segundo plano os eventos da luta e, se ainda não estiverem guardados, os **top 10 do mesmo bracket de item level**. O cliente do WCL é um só por processo, guarda cache e respeita limites de pontos e pausas depois de falha (item 12.8).
3. A fonte dos tops (`services/tops.py`) guarda os tops na memória e no banco por 24 h. Se o log analisado está no top 10, ele sai e entra o 11º (RF21; item 12.13).
4. O `EngineAnalyzer` (`services/analyzer.py`) entrega a luta do jogador e as dos tops ao motor (`engine/`), que mede a luta por fase, aplica as regras do Mago Arcano e do chefe (YAML) com os limites tirados dos próprios tops e monta as tabelas por habilidade e por alvo (RF22).
5. O motor explica a diferença para os tops em % do dano do jogador: **erros + sorte + não explicado** (RF23). O `report.py` monta o `AnalysisResult` (item 12.9).
6. O resultado é salvo no banco e mostrado ao jogador.

## Componentes

| Componente       | Tecnologia                                                    | Responsabilidade                                                                                                               |
| ---------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Frontend         | React + Vite                                                  | Telas, validação de entrada, exibição do relatório                                                                             |
| Backend          | FastAPI (Python)                                              | Rotas, autenticação, orquestração da análise                                                                                   |
| Motor de análise | Python (`backend/app/engine/`)                                | Medidas por fase, regras com limites tirados dos tops, diferença para os tops, tabelas por habilidade e por alvo (ver item 12) |
| Banco            | PostgreSQL (Railway) / SQLite em dev                          | Usuários, análises, cópia dos tops por 24 h                                                                                    |
| Fonte de dados   | API Warcraft Logs v2 (GraphQL), cliente em `backend/app/wcl/` | Lutas, eventos da luta e rankings; no modo exemplo, arquivos de `app/samples/`                                                 |

## Ambientes

* **Desenvolvimento:** SQLite local (`backend/logcoach.db`). Com `DATA_SOURCE=exemplo`, relatório, eventos e tops vêm dos arquivos de `app/samples/` (kill de referência do Harmonist e top 10 do bracket), sem internet; é também o que o CI usa. Com `DATA_SOURCE=wcl`, a API real.
* **Produção e apresentação:** frontend na Vercel (https://logcoach.vercel.app), backend e PostgreSQL na Railway (item 13). Se a internet falhar, a reserva é rodar local com `DATA_SOURCE=exemplo`.
