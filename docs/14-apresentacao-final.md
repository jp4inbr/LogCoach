---
description: Demonstração do projeto e do seu valor para a banca.
---

# 14. Apresentação Final (Banca/Demo)

> Roteiro em slides, do problema à demonstração. Link dos slides: _a adicionar_.

| # | Parte                 | Tempo | Conteúdo                                                                            |
| - | --------------------- | ----- | ----------------------------------------------------------------------------------- |
| 1 | Gancho                | 1 min | Premiações de US$ 300 mil e a Race to World First: desempenho em WoW tem valor real |
| 2 | Problema              | 2 min | Log de combate é dado bruto; ferramentas atuais são rígidas e em inglês             |
| 3 | Público               | 1 min | Jogador brasileiro no nível competitivo                                             |
| 4 | Solução               | 2 min | Regras + comparação com os melhores + IA explicando em português                    |
| 5 | Demo ao vivo          | 5 min | Colar o link do log → escolher a luta → clicar no personagem → resultado (roteiro abaixo) |
| 6 | Usabilidade           | 3 min | Heurísticas aplicadas, tratamento de erros, resultado do SUS                        |
| 7 | IA no desenvolvimento | 2 min | Como usamos e como validamos                                                        |
| 8 | Próximos passos       | 1 min | Mais chefes e especializações, Mítica+, versão em inglês                            |

## Roteiro da demo (parte 5)

1. Colar o link `https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D`. Aparecem as lutas do relatório; as que não podem ser analisadas ficam em cinza, com o motivo.
2. Escolher **Nek'zali Mítico, luta 34** (kill, 6:55).
3. Clicar no personagem **Harmonist** (Mago Arcano, item level 327). Nesse clique o LogCoach já começa a buscar os eventos da luta (pré-busca).
4. Mostrar o resultado:
   - DPS do jogador × média do top 10 do mesmo bracket de item level (326–328).
   - Bloco da diferença: "os tops fizeram 18,0% mais dano: 6,6% de erros + 9,5% de sorte da Seta Prismática + 1,9% não explicado".
   - Erros em ordem de impacto.
   - Nomes dos outros jogadores ocultos por padrão (RF25), com o botão de olho para exibir.
   - Linha do tempo da luta.
   - Todas as regras, cada uma com a referência tirada dos tops (ex.: "mediana dos 10 tops").
   - Tabelas por habilidade e por alvo, em % (jogador × tops).
5. Dizer que o **resumo do coach (IA) ainda não está ligado**: hoje o relatório sai só com as regras (RF17); a explicação em português pelo Gemini é o próximo passo.

## Como rodar a demo

| Parte | Comando |
|---|---|
| Backend | Em `backend/`, com o venv ativo: `uvicorn app.main:app --reload` |
| Frontend | Em `frontend/`: `npm run dev` e abrir http://localhost:5173 |

- **Ensaio antes:** rodar a demo uma vez com internet antes da banca, para guardar no banco os tops do bracket (a cópia vale 24 h) e não depender da busca na hora.
- **Plano B (sem internet ou Warcraft Logs fora do ar):** subir o backend com `DATA_SOURCE=exemplo` no `backend/.env`. O motor real roda sobre o kill de referência e os 10 tops guardados em `backend/app/samples/` (item 13).
- Instalação e `.env`: item 12.1.

**Divisão de fala:** _definir quem apresenta cada parte (todos os integrantes precisam participar)._
