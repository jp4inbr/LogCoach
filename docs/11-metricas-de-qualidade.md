# 11. Métricas de Qualidade

> Entrega da RT03 / banca. Lint, testes, carregamento, tempo de análise e responsividade já medidos (04/11, com o motor na `main`). Testes e cobertura atualizados em 16/11 (CI do PR #31).

<table data-search="false"><thead><tr><th width="184.61663818359375">Métrica</th><th width="105.25">Meta</th><th width="203.85009765625">Como medir</th><th width="246.41656494140625">Resultado</th></tr></thead><tbody><tr><td>Testes passando</td><td>100%</td><td><code>pytest</code> no CI</td><td><strong>100%</strong> — 630 de 630 no backend, com 1 pulado de propósito (16/11), 127 deles do motor; 601 de 601 no Vitest e 47 de 47 no Playwright no frontend (16/11). Ver itens 10.3 e 10.4</td></tr><tr><td>Cobertura de testes do motor de análise</td><td>≥ 70%</td><td><code>pytest --cov=app/engine</code></td><td><strong>99%</strong> — 1.462 linhas em <code>app/engine/</code>, 11 sem teste; backend inteiro 98% (CI, 16/11; ver 10.3)</td></tr><tr><td>Erros de lint</td><td>0</td><td><code>ruff check</code> e <code>eslint</code> no CI</td><td><strong>0</strong> — CI verde no backend e no frontend, Ubuntu e Windows (PR #31, 16/11)</td></tr><tr><td>Tempo de carregamento das páginas</td><td>&#x3C; 3 s (RNF01)</td><td>DevTools do navegador</td><td><strong>0,7 s em 4G e 1,8 s em 3G rápido</strong> — tela inicial, build de produção (mediana de 5 medições, ver 11.1)</td></tr><tr><td>Tempo de uma análise completa</td><td>&#x3C; 2 min (RNF02)</td><td>Log do backend</td><td><strong>~1,1 s</strong> pela rota no modo exemplo (kill de referência); no modo real, com os eventos já pré-buscados e o bracket no cache, a análise só roda o motor. A primeira busca dos tops de um bracket leva até ~2,5 min, mas é feita na pré-busca, em segundo plano (ver 11.3)</td></tr><tr><td>Responsividade</td><td>OK de 360 px a desktop</td><td>Teste manual em celular e PC</td><td><strong>OK</strong> — sem rolagem lateral a 360 px em todas as telas; testado no celular de um integrante (ver 11.2)</td></tr></tbody></table>

## 11.1 Como o tempo de carregamento foi medido

* **O quê:** do pedido da página até a tela inicial aparecer com o título, no Chromium, com cache vazio a cada medição.
* **Versão:** frontend da `main` em 27/10, compilado para produção (JavaScript de 240 KB, 76 KB comprimido), servido sem compressão. Com o sistema publicado e compressão ligada (item 13), o tempo tende a cair.
* **Redes simuladas:** sem limite 0,15 s · 4G (4 Mbps, 20 ms) 0,71 s · 3G rápido (1,6 Mbps, 150 ms) 1,75 s. Todas abaixo da meta de 3 s.
* **Refazer na banca** com o sistema publicado, pela aba Network do DevTools (F12), para medir com a rede real.

## 11.2 Responsividade

Telas conferidas a 360 px de largura (celular pequeno) e a 1100 px (desktop): início, login, escolha da luta, andamento, resultado com as três abas, perfil e planos. Nenhuma rola para o lado; a linha do tempo empilha os rótulos acima das barras no celular.

![Tela inicial a 360 px](.gitbook/assets/11-celular-inicio.png) ![Escolha da luta a 360 px](.gitbook/assets/11-celular-lutas.png)

## 11.3 Tempo de uma análise

* **Modo exemplo** (`DATA_SOURCE=exemplo`): `POST /analyses` com o kill de referência (Harmonist, Nek'zali Mítico, 6:55) contra os 10 tops do bracket leva **\~1,1 s** do pedido à resposta, com o motor completo.
* **Modo real** (`DATA_SOURCE=wcl`): quando a pessoa escolhe o personagem, a pré-busca baixa os eventos da luta e, se o bracket ainda não estiver guardado, os tops (item 12.13). Na hora de analisar, eventos e tops já estão na memória ou no banco (24 h), e a análise roda só o motor.
* **Primeira busca de um bracket:** os 11 tops levaram entre \~53 s e \~2,5 min nas medições de 04/11 (varia com o Warcraft Logs). Como acontece em segundo plano, enquanto a pessoa ainda está na tela de escolha, não entra no tempo da análise; quem analisa antes de ela terminar espera a mesma busca.
