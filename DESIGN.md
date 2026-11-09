---
name: LogCoach
description: Boletim em português do que cada Mago Arcano deve corrigir primeiro, comparado aos melhores do mesmo item level.
colors:
  dark-accent: "#ff8906"
  dark-accent-strong: "#ff9f33"
  dark-accent-ink: "#0f0e17"
  dark-accent-fg: "#ff8906"
  dark-link: "#ff5c8f"
  dark-brand-2: "#e53170"
  dark-top: "#5eead4"
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
  light-top: "#0f766e"
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
  light-warn: "#92400e"
  light-warn-bg: "rgb(180 83 9 / 12%)"
  light-error: "#b91c1c"
  light-error-bg: "rgb(185 28 28 / 9%)"
  light-error-ink: "#fffffe"
  light-info-bg: "rgb(186 232 232 / 45%)"
typography:
  display:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "3rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "2.2rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.2rem"
    fontWeight: 700
    lineHeight: 1.2
  subtitle:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 700
    lineHeight: 1.2
  lead:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.1rem"
    fontWeight: 400
    lineHeight: 1.5
  body:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  small:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.06em"
rounded:
  sm: "8px"
  md: "12px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  gap: "16px"
  lg: "20px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.dark-accent}"
    textColor: "{colors.dark-accent-ink}"
    rounded: "{rounded.sm}"
    padding: "0 18px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.dark-accent-strong}"
    textColor: "{colors.dark-accent-ink}"
  button-default:
    backgroundColor: "{colors.dark-surface-2}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.sm}"
    padding: "0 18px"
    height: "44px"
  button-small:
    backgroundColor: "{colors.dark-surface-2}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    height: "36px"
  button-danger:
    backgroundColor: "{colors.dark-error}"
    textColor: "{colors.dark-error-ink}"
    rounded: "{rounded.sm}"
    padding: "0 18px"
    height: "44px"
  input:
    backgroundColor: "{colors.dark-bg}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    height: "44px"
  card:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.md}"
    padding: "20px"
  mistake-card:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.md}"
    padding: "18px"
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
    backgroundColor: "{colors.dark-warn-bg}"
    textColor: "{colors.dark-warn}"
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

**Creative North Star: "O Boletim do Coach"**

O LogCoach se lê de cima para baixo, como um boletim comentado. Primeiro vem o tamanho da diferença para os melhores, depois cada erro em ordem de custo, com o motivo e o que fazer. Os dados completos ficam um passo abaixo, para quem quiser aprofundar.

O tom é direto e sóbrio. A tela mostra o número e a correção, sem ilustração nem efeito, e a cor só aparece em ação ou em diagnóstico. A confiança vem de deixar claro o que é erro, o que é sorte e o que é hipótese.

A linha do tempo mostra quando cada coisa aconteceu, com o jogador e os tops no mesmo eixo. Ela fica em uma aba própria do resultado, a um clique do Resumo, para que os erros priorizados continuem em primeiro lugar.

Referências rejeitadas: a planilha crua de log, o painel de IA genérico, o visual gamer agressivo e, do imaginário de fantasia, as fontes medievais e o pergaminho.

**Key Characteristics:**

- Uma coluna de leitura, com largura máxima de 960 px.
- Dois temas, escuro e claro, com os mesmos papéis de cor.
- Superfícies planas em camadas tonais, separadas por borda fina.
- Um único destaque de ação por tema.
- Verde, âmbar e vermelho reservados para situação.

## Colors

Fundo neutro e silencioso, um destaque de ação e três cores de situação que nunca mudam de sentido. Os valores dos dois temas estão no topo deste arquivo. A origem, os desvios por contraste e a lista completa, com os tokens decorativos, estão em `docs/15-padrao-de-cores.md`.

### Primary

- **Laranja Âmbar, no escuro, e Amarelo Sinal, no claro** (`--accent`): preenchimento do botão principal e do avatar do coach.
- **Destaque como traço** (`--accent-fg`): texto de destaque, borda de seleção, marca do jogador na linha do tempo e linha do gráfico. No escuro repete o Laranja Âmbar; no claro vira a Tinta Índigo, porque o amarelo não tem contraste sobre fundo claro.

### Secondary

- **Teal dos Tops** (`--top`): tudo o que representa os melhores na comparação.

### Tertiary

- **Rosa Elétrico, no escuro, e Tinta Índigo sublinhada, no claro** (`--link`): links no texto e botões com cara de link.
- **Segunda cor da marca** (`--brand-2`): só no degradê do selo da marca.

### Neutral

- **Noite Azulada, no escuro, e Branco Quente, no claro** (`--bg`): fundo da página e dos campos.
- **Superfície de cartão** (`--surface`): cartões e painéis. Grafite Azulado no escuro, Menta Clara no claro.
- **Superfície elevada** (`--surface-2`): botões comuns, abas, blocos "O que fazer" e seleção. Ardósia no escuro, Água-Marinha no claro.
- **Borda** (`--border`) e **borda de controle** (`--border-control`): a primeira é decorativa, a segunda delimita campos e tem contraste de 3:1.
- **Texto** (`--text`) e **texto de apoio** (`--muted`): títulos e leitura principal; rótulos, dicas e informação secundária.

### Situação

- **Ok** (`--ok`), **Atenção** (`--warn`) e **Erro** (`--error`), cada uma com o fundo translúcido correspondente. O tom muda por tema para passar no contraste, mas o sentido não muda.
- **Luck** (`--luck`): série do azar (RNG) na decomposição da diferença. Azar não é situação e nunca é cobrado como erro, por isso não usa `--warn`. Azul nos dois temas, com o tom ajustado ao contraste de cada um, para ficar distinto de `--error` e de `--muted` também com daltonismo. Séries vizinhas de um gráfico precisam se distinguir entre si, não só do fundo.

**Regra da Situação Fixa.** Verde é ok, âmbar é atenção e vermelho é erro, em qualquer tema e em qualquer tela. Essas cores não servem de decoração.

**Regra do Destaque que Preenche.** `--accent` só preenche. Quando o destaque vira texto, borda ou traço, usa-se `--accent-fg`.

**Regra do Você e dos Tops.** O jogador é sempre o destaque e os melhores são sempre o teal, para que a comparação se leia sem legenda depois da primeira vez.

## Typography

**Display Font:** Inter (com Segoe UI, system-ui e demais fontes do sistema)
**Body Font:** a mesma família
**Label/Mono Font:** não há fonte separada

**Character:** uma família só, neutra e legível, em que a hierarquia vem do peso e do tamanho. Nenhuma fonte web é carregada, então Inter só aparece onde estiver instalada; nos demais casos vale a fonte do sistema.

### Hierarchy

- **Display** (700, de 1,9rem a 3rem com `clamp`, altura 1,2, no máximo 18ch): só o título da tela inicial.
- **Headline** (700, de 1,6rem a 2,2rem com `clamp`, altura 1,2): título principal de cada tela.
- **Title** (700, 1,2rem, altura 1,2): seções, como "Como funciona" e "Erros do maior para o menor impacto".
- **Subtitle** (700, 1,05rem, altura 1,2): título de cada erro e de blocos internos.
- **Lead** (400, 1,1rem, altura 1,5, no máximo 60ch): frase de abertura em `--muted`.
- **Body** (400, 1rem, altura 1,5): explicações e texto corrido. Tabelas usam 0,92rem.
- **Small** (400, 0,85rem): metadados, motivos, dicas e referência das regras.
- **Label** (600, 0,8rem, maiúsculas): cabeçalho de tabela, com espaçamento de 0,04em, e sobretítulo de tela, com 0,06em. Selos usam o mesmo tamanho e peso, sem maiúsculas.

**Regra do Número em Negrito.** O custo e a diferença aparecem em peso forte, dentro de uma frase em português. O número nunca fica solto sem dizer o que significa.

## Layout

Coluna única centralizada de até 960 px, com margem lateral de 16 px e 48 px de respiro no fim do conteúdo. Blocos vizinhos usam 16 px a 20 px entre si, e a tela inicial separa seções com 32 px. Formulários de conta usam um cartão de até 440 px, e a tela de andamento, até 560 px.

Grupos repetidos, como estatísticas, passos e planos, usam grade automática que se ajusta sozinha à largura, sem pontos de quebra próprios. Tabelas largas rolam dentro do próprio contêiner, para a página não rolar na horizontal.

No resultado, a ordem é: cabeçalho da luta, estatísticas, avisos, com quem foi comparado, abas, decomposição da diferença, erros em ordem de custo e hipóteses à parte.

Abaixo de 560 px, a navegação ocupa a linha inteira, o campo do link empilha com o botão e a linha do tempo perde a coluna de rótulos. O piso de largura é 360 px.

**Regra do Boletim.** Diagnóstico primeiro, erros por custo depois, dados completos por último. Nenhuma informação nova entra acima da decomposição da diferença sem mudar o que a pessoa precisa corrigir.

## Elevation & Depth

O sistema é plano. A profundidade vem de camadas tonais, do fundo para `--surface` e depois para `--surface-2`, com borda fina de 1 px. Atrás de tudo há um brilho radial suave no canto superior direito da página.

### Shadow Vocabulary

- **Dica flutuante** (`box-shadow: 0 8px 24px var(--shadow)`): a única sombra real, usada na explicação de termos.
- **Anel de seleção** (`box-shadow: inset 0 0 0 1px var(--accent-fg)`): reforça a borda da luta escolhida.

**Regra do Plano por Padrão.** Cartões não ganham sombra. Só o que flutua sobre o conteúdo projeta sombra.

## Shapes

Cantos suaves e consistentes. Contêineres usam a curva maior e controles usam a menor. Status, contadores e barras são totalmente arredondados. Borda tracejada indica estado provisório, como luta ainda subindo, upload pausado ou recurso que ainda vai chegar.

**Regra das Duas Curvas.** 12 px para o que contém e 8 px para o que se aciona. Valores novos precisam de motivo.

## Components

### Buttons

Sólidos e sem efeito, com alvo de toque confortável.

- **Shape:** curva de controle (8 px), altura mínima de 44 px, ou 36 px na versão pequena.
- **Primary:** preenchido com `--accent` e texto em `--accent-ink`, peso 600. Reservado à ação principal da tela.
- **Default:** `--surface-2` com borda fina. Ao passar o mouse, a borda assume `--accent-fg`.
- **Ghost:** a versão transparente do padrão, para ações secundárias.
- **Danger:** preenchido com `--error`; a versão vazada é usada antes de confirmar uma exclusão.
- **Focus:** contorno de 2 px em `--focus`, afastado 2 px, em todos os elementos interativos.
- **Disabled:** opacidade 0,5. Com `aria-disabled` continua focável e usa opacidade 0,6.

### Chips

- **Style:** selos totalmente arredondados, 0,8rem e peso 600, com fundo translúcido e texto na cor da situação.
- **State:** erro e atenção sempre trazem símbolo e palavra ("✕ Erro", "! Atenção"). "Hipótese" usa o tom de destaque. Kill é verde e wipe é neutro. "Subindo" tem um ponto pulsante, e "Pausado" tem duas barras estáticas.

### Cards / Containers

- **Corner Style:** curva de contêiner (12 px).
- **Background:** `--surface`.
- **Shadow Strategy:** nenhuma, conforme Elevation & Depth.
- **Border:** 1 px em `--border`.
- **Internal Padding:** 20 px no cartão padrão; de 14 a 18 px nos blocos do resultado.

### Inputs / Fields

- **Style:** fundo `--bg`, borda `--border-control` de 1 px, curva de controle e altura de 44 px. O rótulo fica acima, em peso 600.
- **Focus:** contorno padrão em `--focus`.
- **Error / Disabled:** borda em `--error` e mensagem logo abaixo do campo, em `--error`, dizendo o que fazer. Desabilitado usa opacidade 0,5.

### Navigation

Marca à esquerda e links à direita, em `--muted`. O item ativo e o item sob o mouse ganham fundo `--surface-2` e texto `--text`. As abas do resultado são sublinhadas em 2 px com `--accent-fg` quando ativas e rolam na horizontal se faltar espaço. O botão de tema tem alvo de 40 px.

### Notice

Aviso em largura cheia, com título em destaque e corpo em `--muted`. Informativo usa o fundo de informação; atenção e erro usam o fundo e a borda da situação. Dados de exemplo sempre aparecem com aviso.

### Mistake Card

O componente central do boletim. Tem posição na lista, título, selo de severidade, custo em peso 600, explicação, bloco "O que fazer" em `--surface-2` e a tabela Você × Melhores. Uma barra de 4 px no lado esquerdo indica a severidade, em `--warn` ou `--error`. Hipóteses não têm posição na lista e ficam em seção separada.

### Gap Breakdown

Frase com a diferença total, barra de 12 px totalmente arredondada, dividida em erros (`--error`), azar (`--luck`) e não explicado (`--muted`), com 2 px de respiro entre os segmentos, e lista com os valores. A barra soma só as partes positivas; valores a favor do jogador aparecem apenas no texto.

### Timeline

Uma faixa de 44 px por trilha sobre `--bg`, com uma linha central. As marcas do jogador ficam acima da linha, em `--accent-fg`, e as dos tops abaixo, em `--top`. A intermissão aparece hachurada, e as fases, por divisórias finas. Abaixo de 560 px, os rótulos passam para cima da trilha.
### Fight List Item

Linha inteira clicável, com o nome da luta à esquerda e o selo à direita. Selecionada, ganha borda e anel de destaque sobre `--surface-2`. Indisponível, fica em cinza, com opacidade reduzida e o motivo escrito. Subindo ou pausada, usa borda tracejada.

### Term

Palavra com sublinhado pontilhado que revela uma dica curta ao passar o mouse ou focar. Largura máxima de 280 px.

### Motion

Movimento funcional e discreto: troca de tema em 0,2 s, seta de expansão em 0,15 s e pulso só em estado de espera real, como etapa em andamento e luta subindo. Tudo isso é desligado com `prefers-reduced-motion`.

## Do's and Don'ts

### Do:

- **Do** usar sempre `var(--token)` para cor; o teste `src/theme-contrast.test.js` falha com cor fixa.
- **Do** criar todo token novo nos dois temas e nos dois blocos do tema claro.
- **Do** usar `--accent-fg` quando o destaque virar texto, borda ou traço.
- **Do** manter contraste WCAG AA: 4,5:1 para texto e 3:1 para elementos gráficos.
- **Do** acompanhar toda cor de situação com texto, ícone ou selo.
- **Do** manter alvos de toque de pelo menos 44 px em ações principais.
- **Do** escrever o número dentro de uma frase em português que diga o que ele significa.
- **Do** conferir os dois temas e a largura de 360 px depois de qualquer mudança visual.

### Don't:

- **Don't** usar fontes medievais ou textura de pergaminho.
- **Don't** montar tela como planilha crua de log, com tabelas e gráficos sem hierarquia ou sem dizer o que corrigir.
- **Don't** usar a estética de painel de IA genérico: brilhos, degradês roxos, ícones de faísca por toda parte e tom de mágica.
- **Don't** usar o visual gamer agressivo: neon, ângulos cortados, fontes de esport e RGB.
- **Don't** usar verde, âmbar ou vermelho como decoração.
- **Don't** usar `--accent` como cor de texto ou de borda.
- **Don't** colocar sombra em cartões.
- **Don't** apresentar azar como erro nem hipótese como fato; cada um tem seu selo e seu lugar.
