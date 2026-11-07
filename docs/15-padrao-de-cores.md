---
description: Paletas do tema claro e escuro, tokens de cor, desvios por contraste e regras para mexer nas cores.
---

# 15. Padrão de Cores (Tema Claro e Escuro)

O LogCoach tem dois temas, claro e escuro. Todas as cores vivem em tokens (variáveis CSS) em `frontend/src/index.css`. Este documento diz de onde vêm, como o tema é escolhido e o que checar antes de mexer.

## 15.1 Origem das paletas

Pedido do Arthur, com paletas do [Happy Hues](https://www.happyhues.co):

* **Escuro:** [paleta 13](https://www.happyhues.co/palettes/13). Fundo `#0f0e17`, título `#fffffe`, parágrafo `#a7a9be`, botão `#ff8906`, secundária `#f25f4c`, terciária `#e53170`, superfície `#2e2f3e`.
* **Claro:** [paleta 14](https://www.happyhues.co/palettes/14). Fundo `#fffffe`, título `#272343`, parágrafo `#2d334a`, botão `#ffd803`, secundária `#e3f6f5`, terciária `#bae8e8`, contorno `#272343`.

Onde a paleta funciona em contraste, o hex é exatamente o dela. Onde não funciona, o desvio está na seção 15.5.

## 15.2 Como o tema é escolhido

1. **Primeira visita:** segue o sistema (`prefers-color-scheme`). Sem preferência ou sem suporte, vale o escuro.
2. **Botão ☀/☾ no cabeçalho:** alterna e salva a escolha no `localStorage`, chave `logcoach.theme`, valor `light` ou `dark`.
3. **Escolha salva:** vale mais que o sistema. Sem escolha salva, se o sistema mudar com a página aberta, o site acompanha. Com escolha salva, não.
4. **Sem flash:** um script pequeno no `<head>` do `index.html` põe `data-theme` no `<html>` antes da primeira pintura. A mesma lógica está em `src/lib/theme.js`; os dois precisam ficar iguais e o teste confere.
5. **Sem JavaScript:** o CSS funciona sozinho (`:root` é o escuro; `@media (prefers-color-scheme: light)` troca para o claro).
6. **localStorage quebrado** (janela anônima, bloqueio): tudo em `try/catch`; o site funciona igual, só não lembra a escolha.

O tema aplicado também define `color-scheme` (formulários e barra de rolagem nativos) e atualiza `<meta name="theme-color">`.

## 15.3 Tokens

O bloco claro aparece duas vezes no CSS (na media query e em `[data-theme="light"]`) porque o CSS não permite compartilhar. O teste exige que os dois sejam idênticos.

| Token | Escuro | Claro | Onde é usado |
|---|---|---|---|
| `--bg` | `#0f0e17` | `#fffffe` | Fundo da página, campos de texto |
| `--surface` | `#181722` | `#e3f6f5` | Cartões, painéis |
| `--surface-2` | `#2e2f3e` | `#bae8e8` | Botões comuns, abas, realces |
| `--border` | `#3b3c4f` | `#a6dcdc` | Divisórias e bordas de cartões (decorativas) |
| `--border-control` | `#7f8199` | `#5e7385` | Borda dos campos de texto |
| `--text` | `#fffffe` | `#272343` | Texto principal e títulos |
| `--muted` | `#a7a9be` | `#4b5169` | Texto de apoio |
| `--link` | `#ff5c8f` | `#272343` | Links no texto (no claro, sempre sublinhados) |
| `--accent` | `#ff8906` | `#ffd803` | Preenchimento do botão principal e do avatar do coach |
| `--accent-strong` | `#ff9f33` | `#f5c800` | Botão principal ao passar o mouse |
| `--accent-ink` | `#0f0e17` | `#272343` | Texto sobre `--accent` |
| `--accent-fg` | `#ff8906` | `#272343` | Destaque como texto, borda, traço de gráfico e marcas |
| `--focus` | `#ff8906` | `#272343` | Anel de foco do teclado |
| `--brand-2` | `#e53170` | `#bae8e8` | Segunda cor do degradê da marca |
| `--top` | `#5eead4` | `#0f766e` | Cor dos tops na comparação |
| `--ok` | `#4ade80` | `#166534` | Situação: ok |
| `--warn` | `#fde047` | `#92400e` | Situação: atenção |
| `--error` | `#f87171` | `#b91c1c` | Situação: erro |
| `--error-ink` | `#0f0e17` | `#fffffe` | Texto sobre `--error` (botão de perigo) |
| `--ok-bg`, `--warn-bg`, `--error-bg` | situação a 12% | situação a 9–12% | Fundo dos avisos e selos |
| `--warn-border`, `--error-border`, `--accent-border` | situação ou destaque a 35–45% | idem | Bordas de avisos e de lutas selecionadas |
| `--info-bg` | `#ff8906` a 10% | `#bae8e8` a 45% | Fundo de avisos informativos |
| `--glow`, `--coach-bg-1/2`, `--hatch`, `--hatch-strong`, `--accent-glow` | destaque translúcido | idem | Brilho do fundo, cartão do coach, faixa da intermissão, pulso |
| `--shadow` | preto a 45% | `#272343` a 25% | Sombra da dica flutuante |

`--accent` serve só de **preenchimento** (botão, avatar). Quando o destaque vira texto, borda ou traço de gráfico, usa `--accent-fg`, porque o amarelo `#ffd803` sobre fundo claro não tem contraste.

## 15.4 Cores de situação

Ok, atenção e erro continuam **verde, âmbar e vermelho** nos dois temas, com o mesmo significado. Não vêm da paleta por dois motivos:

* **Consistência** (heurística de Nielsen, item 8.1): a pessoa aprende uma vez que verde é ok e vermelho é erro, e isso vale em qualquer tema.
* A paleta tem o laranja como destaque e o amarelo como botão. Usar essas cores para "atenção" confundiria destaque com aviso.

Só o tom muda para passar no contraste de cada fundo. No escuro, o âmbar foi deslocado para amarelo (`#fde047`, antes `#fbbf24`) para não ficar parecido com o laranja do botão (`#ff8906`). No claro, o âmbar é um marrom escuro (`#92400e`), bem diferente do botão amarelo.

Cor nunca é a única pista: erros e avisos sempre têm texto, ícone ou selo.

## 15.5 Desvios da paleta (por contraste)

Meta: WCAG 2.x AA (4,5:1 para texto, 3:1 para elementos gráficos).

| Item da paleta | Problema | O que o LogCoach usa |
|---|---|---|
| Texto `#fffffe` sobre o botão `#ff8906` | 2,38:1 (reprova) | Texto do botão `#0f0e17`: 8,06:1 |
| Botão amarelo `#ffd803` como texto, borda ou linha no claro | cerca de 1,4:1 sobre branco | `--accent-fg` `#272343`: 14,91:1. O amarelo fica só como preenchimento de botão |
| Link `#ffd803` (a paleta clara usa o contorno como link) | Reprova sobre branco | Link no claro `#272343`, sempre sublinhado |
| Link `#e53170` (terciária do escuro) | 4,57:1 no fundo, 4,23:1 em cartão (reprova) | `#ff5c8f`: 6,55:1 no fundo, 6,06:1 em cartão. `#e53170` ficou só na marca (`--brand-2`) |
| Parágrafo claro `#2d334a` | Igual ao texto, sem nível de apoio | `--text` `#272343`; `--muted` `#4b5169` (7,83:1) para apoio |
| Secundária clara `#e3f6f5` e terciária `#bae8e8` | Servem de fundo, não de texto | Viram `--surface` e `--surface-2` |
| Cartões e bordas | A paleta não define | `--surface` escuro `#181722` (entre o fundo e `#2e2f3e`); bordas derivadas |
| Verde, âmbar e vermelho | Fora da paleta (decisão do Arthur, seção 15.4) | Tons ajustados por fundo |
| `--top` (teal) | Fora da paleta; precisa diferir do destaque | `#5eead4` no escuro, `#0f766e` no claro |

## 15.6 Contraste medido

Razões calculadas pelo teste `src/theme-contrast.test.js` com a fórmula de luminância relativa do WCAG. "Mín." é o mínimo exigido. Fundos translúcidos aparecem como `fundo/base`: a cor é composta sobre a base antes de medir.

| Primeiro plano | Fundo | Mín. | Escuro | Claro |
|---|---|---|---|---|
| `--text` | `--bg` | 4.5 | 19.16 | 14.91 |
| `--muted` | `--bg` | 4.5 | 8.27 | 7.83 |
| `--link` | `--bg` | 4.5 | 6.55 | 14.91 |
| `--text` | `--surface` | 4.5 | 17.72 | 13.33 |
| `--muted` | `--surface` | 4.5 | 7.65 | 7.00 |
| `--link` | `--surface` | 4.5 | 6.06 | 13.33 |
| `--text` | `--surface-2` | 4.5 | 13.18 | 11.22 |
| `--muted` | `--surface-2` | 4.5 | 5.69 | 5.89 |
| `--link` | `--surface-2` | 4.5 | 4.51 | 11.22 |
| `--accent-fg` | `--bg` | 4.5 | 8.06 | 14.91 |
| `--ok` | `--bg` | 4.5 | 11.00 | 7.13 |
| `--warn` | `--bg` | 4.5 | 14.54 | 7.09 |
| `--error` | `--bg` | 4.5 | 6.93 | 6.47 |
| `--focus` | `--bg` | 3 | 8.06 | 14.91 |
| `--accent-fg` | `--bg` | 3 | 8.06 | 14.91 |
| `--border-control` | `--bg` | 3 | 5.02 | 4.92 |
| `--top` | `--bg` | 3 | 12.96 | 5.47 |
| `--accent-fg` | `--surface` | 4.5 | 7.46 | 13.33 |
| `--ok` | `--surface` | 4.5 | 10.17 | 6.37 |
| `--warn` | `--surface` | 4.5 | 13.45 | 6.34 |
| `--error` | `--surface` | 4.5 | 6.41 | 5.78 |
| `--focus` | `--surface` | 3 | 7.46 | 13.33 |
| `--accent-fg` | `--surface` | 3 | 7.46 | 13.33 |
| `--border-control` | `--surface` | 3 | 4.65 | 4.40 |
| `--top` | `--surface` | 3 | 11.98 | 4.89 |
| `--accent-ink` | `--accent` | 4.5 | 8.06 | 10.71 |
| `--accent-ink` | `--accent-strong` | 4.5 | 9.36 | 9.34 |
| `--error-ink` | `--error` | 4.5 | 6.93 | 6.47 |
| `--ok` | `--ok-bg/--bg` | 4.5 | 8.93 | 6.12 |
| `--warn` | `--warn-bg/--bg` | 4.5 | 11.25 | 6.01 |
| `--error` | `--error-bg/--bg` | 4.5 | 5.97 | 5.56 |
| `--text` | `--info-bg/--bg` | 4.5 | 16.82 | 13.14 |
| `--text` | `--warn-bg/--bg` | 4.5 | 14.83 | 12.65 |
| `--ok` | `--ok-bg/--surface` | 4.5 | 8.04 | 5.51 |
| `--warn` | `--warn-bg/--surface` | 4.5 | 10.08 | 5.41 |
| `--error` | `--error-bg/--surface` | 4.5 | 5.41 | 4.98 |
| `--text` | `--info-bg/--surface` | 4.5 | 15.27 | 12.34 |
| `--text` | `--warn-bg/--surface` | 4.5 | 13.28 | 11.37 |

## 15.7 Regras para quem for mexer

* **Nunca cor fixa** (hex, `rgb()`) no CSS ou no JSX fora dos blocos de tokens. Sempre `var(--token)`. O teste falha se achar uma.
* **Token novo** entra nos **dois** temas (e nos dois blocos do claro) e, se for texto ou gráfico, entra na lista de pares do teste de contraste.
* Para destaque como texto, borda ou traço, use `--accent-fg`, nunca `--accent`.
* Depois de mexer: `cd frontend && npm test` (o `theme-contrast.test.js` pega contraste, blocos diferentes e cor fixa).
* Se mexer na lógica de escolha do tema, mude `src/lib/theme.js` e o script do `index.html` juntos.
* Confira os dois temas no navegador, inclusive a 360 px de largura.

## 15.8 Onde está o código

| Arquivo | O que tem |
|---|---|
| `frontend/src/index.css` | Tokens dos dois temas e botão de tema |
| `frontend/index.html` | Script inline que evita o flash e `theme-color` |
| `frontend/src/lib/theme.js` | Resolução do tema, `applyTheme`, `saveTheme` e o hook `useTheme()` |
| `frontend/src/components/ThemeToggle.jsx` | Botão no cabeçalho ("Ativar tema claro" / "Ativar tema escuro") |
| `frontend/src/lib/theme.test.js`, `src/components/ThemeToggle.test.jsx`, `src/App.test.jsx` | Testes da escolha, do botão e do cabeçalho |
| `frontend/src/theme-contrast.test.js` | Tokens, contraste e cores-base das paletas |
