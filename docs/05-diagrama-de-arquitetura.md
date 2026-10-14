# 5. Diagrama de Arquitetura

```mermaid
flowchart LR
    U[Jogador<br/>navegador] --> FE[Frontend<br/>React + Vite]
    FE -->|HTTPS / JSON| BE[Backend<br/>FastAPI - Python]

    subgraph GCP[Google Cloud]
        BE
        DB[(PostgreSQL<br/>Cloud SQL)]
        AI[IA<br/>Gemini via Vertex AI]
    end

    BE --> DB
    BE -->|fatos + perguntas| AI
    BE -->|GraphQL + OAuth| WCL[API Warcraft Logs v2]

    subgraph Motor[Motor de análise - dentro do backend]
        R1[Coletor de eventos] --> R2[Linha do tempo<br/>da luta]
        R2 --> R3[Regras do encontro<br/>YAML por chefe]
        R2 --> R4[Regras da spec<br/>YAML Mago Arcano]
        R3 --> R5[Correlacionador<br/>chefe x jogador]
        R4 --> R5
        R5 --> R6[Comparador por fase<br/>com top logs]
    end
    BE --- Motor
```

> Se o diagrama não renderizar no GitBook, ative a integração **Mermaid** no espaço ou exporte uma imagem pelo [mermaid.live](https://mermaid.live).

## Como uma análise funciona

1. O jogador cola o link. O frontend valida o formato e envia ao backend.
2. O backend busca a luta na API do Warcraft Logs e os melhores logs (do cache ou da API).
3. O motor monta a linha do tempo da luta, aplica as regras do encontro e da especialização e cruza os eventos do chefe com os cooldowns do jogador.
4. O comparador mede a diferença para os melhores, fase a fase.
5. Só esses fatos, com as perguntas de julgamento, vão para a IA, que devolve a explicação em português.
6. O resultado é salvo no banco e mostrado ao jogador.

**Por que a IA não recebe o log bruto:** o log tem milhares de eventos. Mandar tudo seria caro e aumentaria o risco de a IA inventar coisas. O código calcula os números e a IA só explica.

## Componentes

| Componente | Tecnologia | Responsabilidade |
|---|---|---|
| Frontend | React + Vite | Telas, validação de entrada, exibição do relatório |
| Backend | FastAPI (Python) | Rotas, autenticação, orquestração da análise |
| Motor de análise | Python (módulo do backend) | Linha do tempo, regras do encontro e da especialização, correlação e comparação por fase (ver item 12) |
| Banco | PostgreSQL (Cloud SQL) / SQLite em dev | Usuários, análises, cache dos top logs |
| IA | Gemini via Vertex AI | Explicar e priorizar os erros em português |
| Fonte de dados | API Warcraft Logs v2 (GraphQL) | Eventos da luta e rankings |

## Ambientes

- **Desenvolvimento:** SQLite local e dados de exemplo salvos em arquivo.
- **Apresentação:** backend no Cloud Run e banco no Cloud SQL, com um log de exemplo já processado como reserva caso a internet falhe.
