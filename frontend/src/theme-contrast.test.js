// Paletas e contraste (docs/15-padrao-de-cores.md): lê os tokens de src/index.css e confere
// WCAG 2.x AA em cada tema, que os dois blocos do tema claro são iguais e que as cores-base
// das paletas do Happy Hues continuam lá.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8");

/** Corpo (entre chaves) do bloco que começa em `selector`. */
function block(selector) {
  const start = css.indexOf(selector);
  if (start < 0) throw new Error(`bloco não encontrado: ${selector}`);
  const open = css.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < css.length; i++) {
    if (css[i] === "{") depth++;
    if (css[i] === "}" && --depth === 0) return css.slice(open + 1, i);
  }
  throw new Error(`bloco sem fim: ${selector}`);
}

function tokens(body) {
  const out = {};
  for (const [, name, value] of body.matchAll(/(--[\w-]+):\s*([^;]+);/g)) out[name] = value.trim();
  return out;
}

const dark = tokens(block(":root {"));
const lightMedia = tokens(block(':root:not([data-theme="dark"]) {'));
const lightAttr = tokens(block(':root[data-theme="light"] {'));
const light = lightAttr;

// ---------- cor e contraste ----------

function parseColor(value) {
  let m = /^#([0-9a-f]{6})$/i.exec(value);
  if (m) {
    const n = parseInt(m[1], 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 };
  }
  m = /^rgb\((\d+)\s+(\d+)\s+(\d+)(?:\s*\/\s*([\d.]+)%)?\)$/.exec(value);
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] / 100 };
  throw new Error(`cor não reconhecida: ${value}`);
}

/** Compõe `fg` (com alfa) sobre `bg` opaco. */
function over(fg, bg) {
  return {
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  };
}

function luminance({ r, g, b }) {
  const [R, G, B] = [r, g, b].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** Cor de um token, composta sobre o token `base` quando tem alfa. */
function color(theme, name, base) {
  const c = parseColor(theme[name]);
  return c.a < 1 ? over(c, color(theme, base)) : c;
}

// [primeiro plano, fundo, mínimo, fundo sobre o qual o fundo translúcido é composto]
const TEXT = 4.5;
const GRAPHIC = 3;
const pairs = [
  ...["--bg", "--surface", "--surface-2"].flatMap((bg) => [
    ["--text", bg, TEXT],
    ["--muted", bg, TEXT],
    ["--link", bg, TEXT],
  ]),
  // Destaque como texto em realces: aba ativa, botão de olho ligado, luta selecionada.
  ["--accent-fg", "--surface-2", TEXT],
  ...["--bg", "--surface"].flatMap((bg) => [
    ["--accent-fg", bg, TEXT],
    ["--ok", bg, TEXT],
    ["--warn", bg, TEXT],
    ["--error", bg, TEXT],
    ["--focus", bg, GRAPHIC],
    ["--accent-fg", bg, GRAPHIC],
    ["--border-control", bg, GRAPHIC],
    ["--top", bg, GRAPHIC],
  ]),
  // Série de azar da barra "De onde vem essa diferença", sobre o fundo da barra e dos pontos.
  ...["--surface-2", "--surface"].map((bg) => ["--luck", bg, GRAPHIC]),
  ["--accent-ink", "--accent", TEXT],
  ["--accent-ink", "--accent-strong", TEXT],
  ["--error-ink", "--error", TEXT],
  // Situação sobre o próprio fundo de realce (translúcido, composto sobre bg e surface).
  ...["--bg", "--surface"].flatMap((base) => [
    ["--ok", "--ok-bg", TEXT, base],
    ["--warn", "--warn-bg", TEXT, base],
    ["--error", "--error-bg", TEXT, base],
    ["--text", "--info-bg", TEXT, base],
    ["--text", "--warn-bg", TEXT, base],
    // Selos e pílulas de destaque (hipótese, enviando) e texto de apoio dentro dos avisos.
    ["--accent-fg", "--info-bg", TEXT, base],
    ["--muted", "--info-bg", TEXT, base],
    ["--muted", "--warn-bg", TEXT, base],
    ["--muted", "--error-bg", TEXT, base],
  ]),
];

const themes = { escuro: dark, claro: light };

describe("tokens dos temas", () => {
  it("os dois blocos do tema claro (media query e data-theme) são idênticos", () => {
    expect(lightMedia).toEqual(lightAttr);
  });

  it("os mesmos tokens de cor existem nos dois temas", () => {
    const colorNames = (t) => Object.keys(t).filter((n) => /^--(?!radius|gap|max)/.test(n));
    expect(colorNames(light).sort()).toEqual(colorNames(dark).sort());
  });

  it.each([
    ["escuro", dark],
    ["claro (media query)", lightMedia],
    ["claro (data-theme)", lightAttr],
  ])(
    "todo token de cor do tema %s é uma cor literal (sem var(), que pode apontar para si)",
    (_n, t) => {
      // Um token que referencia a si mesmo (ex.: --error-border: var(--error-border)) vira
      // valor inválido no navegador sem nenhum aviso; aqui ele não passa no parseColor.
      for (const [name, value] of Object.entries(t)) {
        if (/^--(radius|gap|max)/.test(name)) continue;
        expect(() => parseColor(value), `${name}: ${value}`).not.toThrow();
      }
    },
  );

  it("todo var(--x) usado no CSS está definido nos tokens", () => {
    const used = new Set([...css.matchAll(/var\((--[\w-]+)/g)].map((m) => m[1]));
    const missing = [...used].filter((name) => !(name in dark));
    expect(missing).toEqual([]);
  });

  it("não há cor fixa no CSS fora dos blocos de tokens", () => {
    let rest = css;
    for (const sel of [
      ":root {",
      ':root:not([data-theme="dark"]) {',
      ':root[data-theme="light"] {',
    ]) {
      rest = rest.replace(block(sel), "");
    }
    expect(rest.match(/#[0-9a-fA-F]{3,8}\b|rgba?\(/g)).toBeNull();
  });
});

describe.each(Object.entries(themes))("contraste WCAG AA, tema %s", (_name, theme) => {
  it.each(pairs.map((p) => [`${p[0]} sobre ${p[1]}${p[3] ? ` (sobre ${p[3]})` : ""}`, ...p]))(
    "%s",
    (_label, fg, bg, min, base) => {
      const background = color(theme, bg, base ?? "--bg");
      const foreground = parseColor(theme[fg]);
      const value = ratio(over(foreground, background), background);
      expect(value, `${fg} sobre ${bg}: ${value.toFixed(2)}`).toBeGreaterThanOrEqual(min);
    },
  );
});

// Séries vizinhas da barra da diferença (erros, azar, não explicado): cada uma passar contra o
// fundo não basta, elas precisam se distinguir entre si. Distância em OKLab (perceptual):
// 0,12 normal e 0,10 simulando protanopia e deuteranopia. Os valores antigos do claro
// (--error × --warn: 0,089 normal e 0,024 em protanopia) reprovam; o escuro mede 0,11 ou mais.
const CVD = {
  protanopia: [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
  ],
  deuteranopia: [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.01182, 0.04294, 0.968881],
  ],
};

function oklab(value, matrix) {
  const { r, g, b } = parseColor(value);
  let lin = [r, g, b].map((v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  if (matrix) lin = matrix.map((row) => row[0] * lin[0] + row[1] * lin[1] + row[2] * lin[2]);
  const [l, m, s] = [
    0.4122214708 * lin[0] + 0.5363325363 * lin[1] + 0.0514459929 * lin[2],
    0.2119034982 * lin[0] + 0.6806995451 * lin[1] + 0.1073969566 * lin[2],
    0.0883024619 * lin[0] + 0.2817188376 * lin[1] + 0.6299787005 * lin[2],
  ].map(Math.cbrt);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

function distance(a, b, matrix) {
  const [x, y] = [oklab(a, matrix), oklab(b, matrix)];
  return Math.hypot(...x.map((v, i) => v - y[i]));
}

describe.each(Object.entries(themes))("séries da barra da diferença, tema %s", (_n, theme) => {
  const series = ["--error", "--luck", "--muted"];
  const combos = series.flatMap((a, i) => series.slice(i + 1).map((b) => [a, b]));
  it.each(combos)("%s e %s se distinguem", (a, b) => {
    expect(distance(theme[a], theme[b])).toBeGreaterThanOrEqual(0.12);
    for (const matrix of Object.values(CVD)) {
      expect(distance(theme[a], theme[b], matrix)).toBeGreaterThanOrEqual(0.1);
    }
  });
});

describe("cores-base das paletas do Happy Hues", () => {
  it("escuro = paleta 13", () => {
    expect(dark["--bg"]).toBe("#0f0e17");
    expect(dark["--text"]).toBe("#fffffe");
    expect(dark["--muted"]).toBe("#a7a9be");
    expect(dark["--accent"]).toBe("#ff8906");
    expect(dark["--surface-2"]).toBe("#2e2f3e");
    expect(dark["--brand-2"]).toBe("#e53170");
  });

  it("claro = paleta 14", () => {
    expect(light["--bg"]).toBe("#fffffe");
    expect(light["--text"]).toBe("#272343");
    expect(light["--accent"]).toBe("#ffd803");
    expect(light["--accent-ink"]).toBe("#272343");
    expect(light["--surface"]).toBe("#e3f6f5");
    expect(light["--surface-2"]).toBe("#bae8e8");
  });
});
