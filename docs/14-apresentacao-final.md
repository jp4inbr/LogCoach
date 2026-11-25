---
description: Demonstração do projeto e do seu valor para a banca.
---

# 14. Apresentação Final (Banca/Demo)

A banca tem duas partes, como pediu o professor: **20 minutos de slides**, na ordem do e-mail (itens 1 a 13 abaixo), e **30 minutos de demonstração prática** do aplicativo.

<table data-search="false"><thead><tr><th>#</th><th>Parte</th><th>Tempo</th><th>Conteúdo</th><th>Apresentador</th></tr></thead><tbody><tr><td>1</td><td>Capa</td><td>0,5 min</td><td>EXPOUNA 2026, título, integrantes em ordem alfabética, instituição e data</td><td>Pedro</td></tr><tr><td>2</td><td>Sumário</td><td>0,5 min</td><td>Tópicos da apresentação, com quem apresenta cada bloco</td><td>Pedro</td></tr><tr><td>3</td><td>Introdução</td><td>1,5 min</td><td>WoW em grupo: dungeons e raids (Mítico, 20 jogadores); combate → combat log → Warcraft Logs</td><td>Pedro</td></tr><tr><td>4</td><td>Objetivo do projeto</td><td>1,5 min</td><td>Validar o MVP de set a nov: entregas (Alfa na RT03, Beta na banca), Nek'zali primeiro e metas (SUS ≥ 68, 1ª análise ≤ 5 min, sucesso ≥ 80%, páginas &#x3C; 3 s)</td><td>Pedro</td></tr><tr><td>5</td><td>Problema e pesquisa</td><td>2,5 min</td><td>Log é dado bruto; três caminhos atuais e o custo de cada um; US$ 600 mil em prêmios, 480 mi de horas na Twitch, 51 guildas BR no Mítico</td><td>Pedro</td></tr><tr><td>6</td><td>Fontes de pesquisa</td><td>1 min</td><td>Raider.IO, Warcraft Logs, SullyGnome, Blizzard, TecMundo e o relato do especialista</td><td>Pedro</td></tr><tr><td>7</td><td>Público-alvo e personas</td><td>2 min</td><td>Jogador brasileiro de raide Mítica; personas Rafael e Camila, e Lucas fora do MVP</td><td>Pedro</td></tr><tr><td>8</td><td>Plano de trabalho</td><td>1,5 min</td><td>Cronograma de setembro a novembro, abrindo a planilha</td><td>Luis</td></tr><tr><td>9</td><td>Relatório técnico de IA</td><td>2,5 min</td><td>Claude (Opus 5.5 e Sonnet 5.5), como foi usado e como o grupo validou (PR + CI); IA saiu do produto em 21/11 pelo custo</td><td>Arthur</td></tr><tr><td>10</td><td>Desenvolvimento do software</td><td>3 min</td><td>Arquitetura, tecnologias, desempenho, testes e hospedagem (Vercel + Railway)</td><td>Arthur</td></tr><tr><td>11</td><td>Conclusão</td><td>2 min</td><td>Entregue, dificuldades, lições e análise dos integrantes</td><td>Arthur</td></tr><tr><td>12</td><td>Objetivo × resultado</td><td>1 min</td><td>Cada item do objetivo com o resultado (só os 2 chefes extras não foram atingidos)</td><td>Arthur</td></tr><tr><td>13</td><td>Referências</td><td>0,5 min</td><td>Lista em ABNT (completa no item 1.5)</td><td>Arthur</td></tr><tr><td>14</td><td>Demonstração prática</td><td>30 min</td><td>Roteiro abaixo</td><td>Grupo</td></tr></tbody></table>

## Roteiro da demo (parte 14)

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
