---
name: LogCoach
description: Diagnóstico em português do que cada Mago Arcano deve corrigir primeiro, com a diferença para os melhores do mesmo item level sob a luz.
colors:
  dark-accent: "#ff8906"
  dark-accent-strong: "#ff9f33"
  dark-accent-ink: "#0f0e17"
  dark-accent-fg: "#ff8906"
  dark-link: "#ff5c8f"
  dark-brand-2: "#e53170"
  dark-top: "#22d3ee"
  dark-bg: "#0f0e17"
  dark-surface: "#181722"
  dark-surface-2: "#2e2f3e"
  dark-border: "#3b3c4f"
  dark-border-control: "#7f8199"
  dark-text: "#fffffe"
  dark-muted: "#a7a9be"
  dark-ok: "#4ade80"
  dark-ok-bg: "rgb(74 222 128 / 12%)"
  dark-luck: "#3b82f6"
  dark-warn: "#fde047"
  dark-warn-bg: "rgb(253 224 71 / 12%)"
  dark-error: "#f87171"
  dark-error-bg: "rgb(248 113 113 / 12%)"
  dark-error-ink: "#0f0e17"
  dark-info-bg: "rgb(255 137 6 / 10%)"
  light-accent: "#ffd803"
  light-accent-strong: "#f5c800"
  light-accent-ink: "#272343"
  light-accent-fg: "#272343"
  light-link: "#272343"
  light-brand-2: "#bae8e8"
  light-top: "#0c7c9c"
  light-bg: "#fffffe"
  light-surface: "#e3f6f5"
  light-surface-2: "#bae8e8"
  light-border: "#a6dcdc"
  light-border-control: "#5e7385"
  light-text: "#272343"
  light-muted: "#4b5169"
  light-ok: "#166534"
  light-ok-bg: "rgb(22 101 52 / 10%)"
  light-luck: "#2563eb"
  light-warn: "#dfa800"
  light-warn-badge-bg: "#ffefa8"
  light-warn-badge-fg: "#9a5b00"
  light-player: "#dd6b00"
  dark-warn-badge-bg: "rgb(253 224 71 / 12%)"
  dark-warn-badge-fg: "#fde047"
  dark-player: "#ff8906"
  light-warn-bg: "rgb(180 83 9 / 12%)"
  light-error: "#b91c1c"
  light-error-bg: "rgb(185 28 28 / 9%)"
  light-error-ink: "#fffffe"
  light-info-bg: "rgb(186 232 232 / 45%)"
  dark-warn-fg: "#fde047"
  light-warn-fg: "#8a5000"
  dark-glow-1: "rgb(255 137 6 / 20%)"
  dark-glow-2: "rgb(242 95 76 / 11%)"
  light-glow-1: "rgb(255 216 3 / 36%)"
  light-glow-2: "rgb(186 232 232 / 55%)"
  dark-glass: "rgb(24 23 34 / 72%)"
  dark-glass-2: "rgb(46 47 62 / 58%)"
  dark-glass-border: "rgb(255 255 254 / 9%)"
  light-glass: "rgb(227 246 245 / 74%)"
  light-glass-2: "rgb(186 232 232 / 60%)"
  light-glass-border: "rgb(39 35 67 / 12%)"
typography:
  display:
    fontFamily: '"Archivo Variable", Archivo Fallback, Segoe UI, system-ui, sans-serif'
    fontSize: "clamp(2.25rem, 1.2rem + 4.4vw, 4rem)"
    fontWeight: 800
    fontStretch: "125%"
    lineHeight: 1.02
    letterSpacing: "-0.02em"
  headline:
    fontFamily: '"Archivo Variable", Archivo Fallback, Segoe UI, system-ui, sans-serif'
    fontSize: "2.125rem"
    fontWeight: 800
    fontStretch: "118%"
    lineHeight: 1.08
    letterSpacing: "-0.015em"
  title:
    fontFamily: '"Archivo Variable", Archivo Fallback, Segoe UI, system-ui, sans-serif'
    fontSize: "1.375rem"
    fontWeight: 750
    fontStretch: "118%"
    lineHeight: 1.15
  subtitle:
    fontFamily: '"Archivo Variable", Archivo Fallback, Segoe UI, system-ui, sans-serif'
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: '"Archivo Variable", Archivo Fallback, Segoe UI, system-ui, sans-serif'
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  small:
    fontFamily: '"Archivo Variable", Archivo Fallback, Segoe UI, system-ui, sans-serif'
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: '"Archivo Variable", Archivo Fallback, Segoe UI, system-ui, sans-serif'
    fontSize: "0.8125rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.04em"
  brand:
    fontFamily: '"Archivo Variable", Archivo Fallback, Segoe UI, system-ui, sans-serif'
    fontSize: "1.125rem"
    fontWeight: 800
    fontStretch: "125%"
    lineHeight: 1
    letterSpacing: "0.02em"
rounded:
  sm: "8px"
  md: "16px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  gap: "16px"
  lg: "24px"
  xl: "32px"
  section: "72px"
components:
  button-primary:
    backgroundColor: "{colors.dark-accent}"
    textColor: "{colors.dark-accent-ink}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.dark-accent-strong}"
    textColor: "{colors.dark-accent-ink}"
  button-default:
    backgroundColor: "{colors.dark-surface-2}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  button-danger:
    backgroundColor: "{colors.dark-error}"
    textColor: "{colors.dark-error-ink}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  input:
    backgroundColor: "{colors.dark-bg}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.pill}"
    padding: "0 18px"
    height: "44px"
  link-pill:
    backgroundColor: "{colors.dark-glass}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.pill}"
    padding: "5px"
    height: "58px"
  panel:
    backgroundColor: "{colors.dark-glass}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.md}"
    padding: "20px"
  mistake-card:
    backgroundColor: "{colors.dark-glass}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.md}"
    padding: "22px 24px"
  mistake-rail:
    backgroundColor: "{colors.dark-glass-2}"
    textColor: "{colors.dark-warn-fg}"
    rounded: "28px"
    padding: "6px"
  theme-switch:
    backgroundColor: "{colors.dark-glass-2}"
    textColor: "{colors.dark-bg}"
    rounded: "{rounded.pill}"
    height: "30px"
  notice:
    backgroundColor: "{colors.dark-info-bg}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.md}"
    padding: "14px 16px"
  badge-ok:
    backgroundColor: "{colors.dark-ok-bg}"
    textColor: "{colors.dark-ok}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
    typography: "{typography.label}"
  badge-warn:
    backgroundColor: "{colors.dark-warn-badge-bg}"
    textColor: "{colors.dark-warn-badge-fg}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
  badge-error:
    backgroundColor: "{colors.dark-error-bg}"
    textColor: "{colors.dark-error}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
---

# Design System: LogCoach

## Overview

**Creative North Star: "A Sala com uma Lâmpada"**

Cada tela é um quarto escuro (ou, no tema claro, uma sala ao sol) com uma única fonte de luz quente, e ela cai sobre o que importa ali. Na tela inicial, sobre o título e o campo do link. No resultado, sobre a frase da diferença para os tops ("Os tops fizeram 18% mais dano que você"), que acende antes de tudo; logo abaixo vêm os erros em ordem de custo, cada um com o número da posição grande, e um trilho numerado leva de um para o outro. O log do jogador é o objeto sob a luz.

O resto fica quieto: fundo liso, painéis translúcidos por onde a luz passa, texto neutro, e a cor só aparece em ação ou em diagnóstico. A marca é tipográfica, "LOGCOACH" em caixa alta numa sans larga e pesada, e o cabeçalho tem três pontos: marca, contexto apagado no centro e a chave de tema em pílula. A confiança continua vindo de deixar claro o que é erro, o que é sorte e o que é hipótese.

O vocabulário veio da inspiração do usuário (o site "Five Years" do estúdio Porto Rocha): a luz única, a marca larga, o cabeçalho de três pontos, o trilho numerado translúcido e o vazio generoso. Ficaram de fora a fotografia e tudo o que não é dado do produto.

Referências rejeitadas: o painel de estatísticas em cartões iguais, a planilha crua de log, o painel de IA genérico (faíscas, degradês roxos), o visual gamer agressivo (neon, ângulos cortados, fontes de esport) e, do imaginário de fantasia, as fontes medievais e o pergaminho.

**Key Characteristics:**

- Uma luz quente por tela (`.lit`), presa ao assunto dela; fundo da página liso em `--bg`.
- Painéis e pílulas translúcidos com desfoque leve, e fundo sólido quando o navegador não tem `backdrop-filter`.
- Uma família, a Archivo variável: larga para a marca, os títulos e os números; normal para a leitura.
- Coluna de leitura de 960 px dentro de uma moldura de 1240 px (cabeçalho e rodapé).
- Controles em pílula, contêineres com cantos de 16 px.
- Verde, âmbar e vermelho reservados para situação; jogador laranja, tops ciano.

## Colors

As duas paletas do Happy Hues continuam (decisão do usuário): a 13 no escuro e a 14 no claro, com os valores-base travados pelo teste. A luz é feita das cores da própria paleta: laranja `#ff8906` e coral `#f25f4c` no escuro, amarelo `#ffd803` e água-marinha `#bae8e8` no claro, como luz do dia. Os valores dos dois temas estão no topo deste arquivo; a origem, os desvios por contraste e o contraste medido de cada par estão em `docs/15-padrao-de-cores.md`.

### Primary

- **Laranja Âmbar, no escuro, e Amarelo Sinal, no claro** (`--accent`): preenchimento do botão principal, do avatar do coach e da seleção de texto.
- **Destaque como traço** (`--accent-fg`): texto de destaque, borda de seleção, número dos passos e linha do gráfico. No escuro repete o laranja; no claro vira a Tinta Índigo.

### Secondary

- **Ciano dos Tops** (`--top`) e **Laranja do Jogador** (`--player`): a comparação na linha do tempo.

### Tertiary

- **Rosa Elétrico, no escuro, e Tinta Índigo sublinhada, no claro** (`--link`): links no texto.
- **Segunda cor da marca** (`--brand-2`): reserva da paleta; a marca agora é só tipográfica.

### Neutral

- **Noite Azulada / Branco Quente** (`--bg`): fundo da página e dos campos. O `body` é sempre só este token.
- **Luz** (`--glow-1` no centro, `--glow-2` na borda): degradê radial atrás do assunto da tela. A opacidade é a mais alta que mantém o texto AA por cima (o link rosa no centro da luz mede 4,77:1).
- **Vidro** (`--glass`, `--glass-2`, `--glass-border`): painéis (cartões, erros, tabelas, lutas) e pílulas (navegação, chave de tema, trilho). Sem `backdrop-filter`, o painel cai para `--surface`.
- **Superfície** (`--surface`, `--surface-2`): reserva sólida do vidro, botões comuns, bloco "O que fazer" e realces.
- **Borda** (`--border`, decorativa) e **borda de controle** (`--border-control`, 3:1, campos e o trilho da chave de tema).
- **Texto** (`--text`) e **texto de apoio** (`--muted`).

### Situação

- **Ok** (`--ok`), **Atenção** (`--warn` para preencher, `--warn-fg` para texto, `--warn-badge-*` para o selo) e **Erro** (`--error`), cada uma com o fundo translúcido correspondente.
- **Azar** (`--luck`): série do RNG na decomposição; azul nos dois temas, nunca situação.

**Regra da Situação Fixa.** Verde é ok, âmbar é atenção e vermelho é erro, em qualquer tema e em qualquer tela. Essas cores não servem de decoração.

**Regra da Situação Inconfundível.** Ok, atenção e erro se distinguem entre si e das outras cores do sistema, com distância medida pelo teste. Com daltonismo, quem garante a leitura é o símbolo e a palavra do selo.

**Regra do Destaque que Preenche.** `--accent` só preenche. Quando o destaque vira texto, borda ou traço, usa-se `--accent-fg`.

**Regra do Você e dos Tops.** O jogador é sempre laranja e os melhores são sempre ciano.

**Regra da Lâmpada Única.** Uma `.lit` por tela, no assunto dela. Duas luzes viram decoração; luz atrás de texto nunca passa de `--glow-1`.

## Typography

**Display Font:** Archivo variável (`"Archivo Variable"`), auto-hospedada pelo npm (`@fontsource-variable/archivo`, OFL), só o subconjunto latin: um arquivo de ~90 kB com os eixos de peso (100–900) e largura (62–125%).
**Body Font:** a mesma família, na largura normal.
**Label/Mono Font:** não há; números usam `tabular-nums`.

**Character:** um grotesco com eixo de largura. Esticado a 118–125% e em peso 800, vira a voz da marca e dos títulos, larga e pesada como a da inspiração; na largura normal, é uma fonte de leitura sóbria. A reserva (`Archivo Fallback`) é a Arial com métricas ajustadas para a troca não pular a página.

### Hierarchy

- **Brand** (800, 1,125rem, largura 125%, caixa alta, +0,02em): só "LOGCOACH" no cabeçalho.
- **Display** (800, de 2,25rem a 4rem com `clamp`, largura 125%, altura 1,02, até 15ch): só o título da tela inicial.
- **Headline** (800, 2,125rem, largura 118%; 1,75rem no celular): título de cada tela e a frase da diferença para os tops.
- **Title** (750, 1,375rem, largura 118%): seções e os números das estatísticas.
- **Subtitle** (700, 1,125rem): título de cada erro, passos, frase de apoio.
- **Body** (400, 1rem, altura 1,55, até 68ch): explicações e texto corrido.
- **Small** (400, 0,875rem): metadados, motivos, dicas, tabelas.
- **Label** (600, 0,8125rem): cabeçalho de tabela (maiúsculas, +0,04em) e selos.
- **Número de posição** (800, 2,75rem, largura 125%; 2rem no celular): o número de cada erro, na cor da situação.

Títulos usam `text-wrap: balance`, parágrafos `text-wrap: pretty`. Tamanhos vivem em tokens (`--size-*`) no `:root`.

**Regra do Número em Negrito.** O custo e a diferença aparecem em peso forte, dentro de uma frase em português. O número nunca fica solto sem dizer o que significa.

## Layout

Cabeçalho e rodapé numa moldura de até 1240 px; o conteúdo numa coluna de até 960 px, com 16 px de margem lateral. O cabeçalho é uma grade de três pontos: marca à esquerda, contexto ("Coach de logs para Mago Arcano") centralizado em `--muted`, navegação e chave de tema à direita. Até 860 px o contexto desce para baixo da marca; até 560 px fica à direita da marca e a navegação ocupa a linha de baixo, podendo quebrar.

**Início.** Primeira dobra centralizada sob a luz: título display, frase de apoio e o campo do link numa pílula larga (até 720 px) com o botão Analisar dentro. "Como funciona" fica abaixo da dobra, como uma linha de três passos com número na fonte larga e um fio fino em cima; o que já é suportado é uma linha discreta no fim.

**Resultado.** Título do chefe, linha de dados (jogador · spec · item level, e dificuldade · Kill em tempo, verde quando é kill), estatísticas numa linha compacta separada por fios, avisos, com quem foi comparado, abas, a diferença sob a luz, os erros por custo e as hipóteses à parte. O trilho dos erros fica fixo à esquerda, fora da coluna, a partir de 1100 px; abaixo disso é uma faixa no topo da lista.

**Demais telas.** Escolher luta: título do relatório com o código embaixo, lista de lutas e de personagens em painéis sob a luz. Conta: cartão de 440 px centralizado sob a luz. Perfil e planos: painéis.

Tabelas largas rolam dentro do próprio contêiner. Nenhuma tela rola de lado em 360 px (testado no e2e, nas sete telas, nos dois temas).

**Regra do Boletim.** Diagnóstico primeiro, erros por custo depois, dados completos por último. Nada novo entra acima da decomposição da diferença.

## Elevation & Depth

A profundidade vem da luz e do vidro, não de sombra. A luz é uma camada atrás de todo o conteúdo da tela (o `.app` isola a camada); os painéis deixam a luz passar com `backdrop-filter: blur(14px)` e um contorno fino em `--glass-border`. Painel sob o mouse ou o foco sobe de camada, para a dica de um termo não ficar por baixo do painel seguinte.

### Shadow Vocabulary

- **Dica flutuante** (`box-shadow: 0 8px 24px var(--shadow)`): a única sombra real, na explicação de termos.
- **Anel de seleção** (`box-shadow: inset 0 0 0 1px var(--accent-fg)`): reforça a borda da luta escolhida.
- **Anel do trilho** (`box-shadow: inset 0 0 0 2px currentcolor`): marca o erro que está sendo lido, na cor da situação.

**Regra do Vidro com Reserva.** Fundo translúcido só dentro de `@supports (backdrop-filter: ...)`; fora dele, o painel é sólido.

## Shapes

**Regra da Pílula e do Painel.** O que se aciona é pílula (botões, campos, navegação, chave de tema, selos, trilho); o que contém tem cantos de 16 px (painéis, cartões de erro, avisos, tabelas). Borda tracejada continua indicando estado provisório: luta subindo, upload pausado, recurso que ainda vai chegar.

## Components

### Buttons

- **Shape:** pílula, altura mínima de 44 px (36 px na versão pequena, só dentro de painéis e avisos).
- **Primary:** `--accent` com texto `--accent-ink`, peso 600. Só a ação principal da tela.
- **Default / Ghost:** `--surface-2` ou transparente, borda fina; ao passar o mouse a borda assume `--accent-fg`.
- **Danger:** `--error` preenchido; vazado antes de confirmar a exclusão.
- **Focus:** contorno de 2 px em `--focus`, afastado 2 px, em tudo o que é interativo.
- **Disabled:** opacidade 0,5 (0,6 com `aria-disabled`, que continua focável).

### Theme Switch

Chave em pílula de 52 × 30 px dentro de um botão de 56 × 44 px: trilho translúcido com borda de controle e uma bolinha em `--text` com o ícone do tema que o clique ativa. No escuro a bolinha fica à esquerda, no claro à direita, com 0,25 s de deslize (nenhum com `prefers-reduced-motion`). O contrato é de botão: nome "Ativar tema claro" / "Ativar tema escuro".

### Link Pill

O campo do link da tela inicial: pílula com o campo transparente e o botão Analisar dentro. O anel de foco vale para a pílula inteira; link inválido pinta a borda de `--error` e a mensagem aparece logo abaixo. No celular, campo e botão viram duas pílulas empilhadas.

### Icons

`components/Icon.jsx`: um só conjunto desenhado em SVG, grade de 24, traço de 2, pontas redondas, cor do texto, `aria-hidden` (com `label` vira `role="img"`). Nenhum glifo Unicode faz papel de ícone.

### Chips

Selos em pílula, 0,8125rem, peso 600. Erro e atenção sempre com símbolo desenhado e palavra ("Erro", "Atenção"); "Hipótese" no tom de destaque; kill verde, wipe neutro; "Subindo…" com ponto pulsante, "Upload pausado" com duas barras.

### Stats Line

As quatro estatísticas do resultado numa linha só, entre dois fios: rótulo pequeno em `--muted` em cima, número na fonte larga embaixo, fios verticais entre elas. No celular, 2 × 2.

### Gap Breakdown

Sem painel, sob a luz da tela: a frase da diferença em headline larga, com o número em `--error` (ou `--ok` a favor), "De onde vem essa diferença" logo abaixo, a barra de 14 px (erros, azar, não explicado, com 2 px de respiro) e a lista das três partes lado a lado.

### Mistake Card

Painel translúcido com o número da posição grande à esquerda, na fonte larga e na cor da situação (`--error` ou `--warn-fg`), título, selo, custo em peso 650, explicação até 68ch, bloco "O que fazer" em `--surface-2` e a tabela Você × Melhores. Sem faixa colorida lateral. Cada cartão tem `id="erro-N"` e recebe o foco quando o trilho leva até ele. Hipóteses não têm número e ficam em seção à parte.

### Mistake Rail

`nav` "Erros por custo": um link de 44 px por erro, na ordem de custo, com o número na cor da situação e o nome acessível "N. título". A partir de 1100 px é uma pílula vertical translúcida fixa à esquerda; abaixo, uma faixa que rola com a lista. O erro no meio da tela fica marcado com `aria-current` e um anel (IntersectionObserver; sem suporte, nenhum). O clique rola até o cartão (suave só sem `prefers-reduced-motion`) e não troca o hash da rota. Só na aba Resumo e com dois erros ou mais.

### Navigation

Links do cabeçalho em pílula de 44 px, em `--muted`; o item atual e o item sob o mouse ganham `--glass-2` e `--text`. Abas do resultado sublinhadas em 2 px com `--accent-fg`.

### Notice, Fight List Item, Term, Timeline

Avisos com fundo de informação, atenção ou erro e corpo em `--muted`; dados de exemplo sempre com aviso. Luta como painel clicável inteiro com selo à direita; escolhida com borda e anel de destaque, indisponível em cinza com o motivo escrito, subindo e pausada com borda tracejada. Termo com sublinhado pontilhado e dica de até 280 px. Linha do tempo com o jogador acima e os tops abaixo no mesmo eixo.

### Motion

Funcional e curto: troca de tema em 0,2 s, deslize da chave em 0,25 s, seta de expansão em 0,15 s, rolagem suave do trilho e pulso só em espera real (etapa em andamento, luta subindo). Tudo desligado com `prefers-reduced-motion`.

## Do's and Don'ts

### Do:

- **Do** usar sempre `var(--token)` para cor, inclusive dentro de `radial-gradient(...)`; o teste `src/theme-contrast.test.js` falha com cor fixa.
- **Do** criar todo token novo nos três blocos (`:root`, a media query clara e `[data-theme="light"]`), com os dois blocos claros idênticos.
- **Do** pôr uma `.lit` por tela, no assunto dela.
- **Do** dar reserva sólida a todo vidro.
- **Do** usar `--accent-fg` quando o destaque virar texto, borda ou traço, e `--warn-fg` quando a atenção virar texto.
- **Do** manter contraste WCAG AA nos dois temas, também sobre a luz e o vidro.
- **Do** acompanhar toda cor de situação com texto, ícone ou selo.
- **Do** manter alvos de 44 px nas ações principais e no trilho.
- **Do** escrever o número dentro de uma frase em português que diga o que ele significa.
- **Do** conferir os dois temas e 360 px depois de qualquer mudança visual.

### Don't:

- **Don't** usar sobretítulo (rótulo pequeno acima do título); a informação vai para a linha de dados ou para o cabeçalho.
- **Don't** usar faixa colorida lateral (mais de 1 px) em cartões, avisos ou itens de lista.
- **Don't** montar estatísticas como cartões iguais lado a lado.
- **Don't** usar glifo Unicode ou emoji como ícone.
- **Don't** espalhar luz, brilho ou degradê como decoração; nada de degradê roxo, faíscas ou neon.
- **Don't** usar fontes medievais, pergaminho ou o visual gamer agressivo.
- **Don't** usar verde, âmbar ou vermelho como decoração, nem `--accent` como texto ou borda.
- **Don't** colocar sombra em cartões.
- **Don't** apresentar azar como erro nem hipótese como fato.
