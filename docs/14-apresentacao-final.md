---
description: Demonstração do projeto e do seu valor para a banca.
---

# 14. Apresentação Final (Banca/Demo)

> Roteiro em slides, do problema à demonstração.

<table data-search="false"><thead><tr><th width="55">#</th><th width="194.9166259765625">Parte</th><th width="87.86669921875">Tempo</th><th width="401.4832763671875">Conteúdo</th></tr></thead><tbody><tr><td>1</td><td>Gancho</td><td>1 min</td><td>Premiações de US$ 300 mil e a Race to World First: desempenho em WoW tem valor real</td></tr><tr><td>2</td><td>Problema</td><td>2 min</td><td>Log de combate é dado bruto; ferramentas atuais são rígidas e em inglês</td></tr><tr><td>3</td><td>Público</td><td>1 min</td><td>Jogador brasileiro no nível competitivo</td></tr><tr><td>4</td><td>Solução</td><td>2 min</td><td>Regras + comparação com os melhores</td></tr><tr><td>5</td><td>Demo ao vivo</td><td>5 min</td><td>Colar o link do log → escolher a luta → clicar no personagem → resultado (roteiro abaixo)</td></tr><tr><td>6</td><td>Usabilidade</td><td>3 min</td><td>Heurísticas aplicadas, tratamento de erros, resultado do teste com usuários</td></tr><tr><td>7</td><td>IA no desenvolvimento</td><td>2 min</td><td>Como usamos e como validamos</td></tr><tr><td>8</td><td>Próximos passos</td><td>1 min</td><td>Mais chefes e especializações, Mítica+, versão em inglês</td></tr></tbody></table>

## Roteiro da demo (parte 5)

1. Colar o link `https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D`. Aparecem as lutas do relatório; as que não podem ser analisadas ficam em cinza, com o motivo.
2. Escolher **Nek'zali Mítico, luta 34** (kill, 6:55).
3. Clicar no personagem **Harmonist** (Mago Arcano, item level 327). Nesse clique o LogCoach já começa a buscar os eventos da luta (pré-busca).
4. Mostrar o resultado:
   * DPS do jogador × média do top 10 do mesmo bracket de item level (326–328).
   * Bloco da diferença: "os tops fizeram 18,0% mais dano: 6,6% de erros + 9,5% de sorte da Seta Prismática + 1,9% não explicado".
   * Erros em ordem de impacto.
   * Nomes dos outros jogadores ocultos por padrão (RF25), com o botão de olho para exibir.
   * Linha do tempo da luta.
   * Todas as regras, cada uma com a referência tirada dos tops (ex.: "mediana dos 10 tops").
   * Tabelas por habilidade e por alvo, em % (jogador × tops).

## Como rodar a demo

<table><thead><tr><th width="147.85003662109375">Parte</th><th width="587.8165893554688">Comando</th></tr></thead><tbody><tr><td>Backend</td><td>Em <code>backend/</code>, com o venv ativo: <code>uvicorn app.main:app --reload</code></td></tr><tr><td>Frontend</td><td>Em <code>frontend/</code>: <code>npm run dev</code> e abrir http://localhost:5173</td></tr></tbody></table>

* **Ensaio antes:** rodar a demo uma vez com internet antes da banca, para guardar no banco os tops do bracket (a cópia vale 24 h) e não depender da busca na hora.
* **Plano B (sem internet ou Warcraft Logs fora do ar):** subir o backend com `DATA_SOURCE=exemplo` no `backend/.env`. O motor real roda sobre o kill de referência e os 10 tops guardados em `backend/app/samples/` (item 13).
* Instalação e `.env`: item 12.1.
