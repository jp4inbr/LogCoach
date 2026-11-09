// Apoio dos testes ponta a ponta: a API do backend simulada no navegador (page.route) e a
// checagem de acessibilidade com o axe-core, com a regra de contraste LIGADA (no jsdom ela
// não roda, porque ele não calcula estilos).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const API = "http://api.test";
export const REPORT_CODE = "XhrmBaYkGCAQjH2D";
export const REPORT_LINK = `https://www.warcraftlogs.com/reports/${REPORT_CODE}#fight=34`;

const AXE_PATH = fileURLToPath(new URL("../node_modules/axe-core/axe.min.js", import.meta.url));

function fixture(name) {
  return JSON.parse(
    readFileSync(fileURLToPath(new URL(`../src/test/fixtures/${name}`, import.meta.url)), "utf8"),
  );
}

// Respostas reais da API no modo exemplo. Cada chamada devolve uma cópia nova.
export const report = () => fixture("report.json");
export const players = () => fixture("players.json");
export const analysis = () => fixture("analysis.json");

// Resposta de erro da API: { detail: { code, message } } (item 12.3).
export function apiError(status, code, message) {
  return { status, body: { detail: { code, message } } };
}

// Rotas do fluxo feliz com o kill de referência.
export function happyRoutes() {
  const result = analysis();
  return {
    "POST /reports/resolve": { body: report() },
    [`GET /reports/${REPORT_CODE}/fights/34/players`]: { body: players() },
    [`POST /reports/${REPORT_CODE}/fights/34/prefetch`]: {
      status: 202,
      body: { status: "started" },
    },
    "POST /analyses": { body: result },
    [`GET /analyses/${result.id}`]: { body: result },
  };
}

/**
 * Simula a API em http://api.test. `routes`: { "MÉTODO /caminho": resposta | [respostas] |
 * (chamada) => resposta }, com resposta = { status = 200, body, delay }. Lista de respostas:
 * uma por chamada, repetindo a última. Chamada sem rota vira 599 e fica em `unmatched`.
 * O navegador trata api.test como outra origem, então a simulação responde também o preflight
 * do CORS e manda os cabeçalhos de permissão.
 */
export async function mockApi(page, routes = {}) {
  const calls = [];
  const unmatched = [];
  const used = new Map();

  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const origin = request.headers().origin ?? "*";
    const cors = {
      "access-control-allow-origin": origin,
      "access-control-allow-headers": "authorization, content-type",
      "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
    };
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: cors });
      return;
    }

    const url = new URL(request.url());
    const key = `${request.method()} ${url.pathname}`;
    const call = {
      key,
      authorization: request.headers().authorization ?? null,
      body: request.postData() ? JSON.parse(request.postData()) : undefined,
    };
    calls.push(call);

    const entry = routes[key];
    if (entry === undefined) {
      unmatched.push(key);
      await route.fulfill({ status: 599, headers: cors, body: "sem rota simulada" });
      return;
    }
    const index = used.get(key) ?? 0;
    used.set(key, index + 1);
    let answer = Array.isArray(entry) ? entry[Math.min(index, entry.length - 1)] : entry;
    if (typeof answer === "function") answer = await answer(call, index);
    if (answer.delay) await new Promise((resolve) => setTimeout(resolve, answer.delay));
    await route.fulfill({
      status: answer.status ?? 200,
      headers: { ...cors, "content-type": "application/json" },
      body: answer.status === 204 ? undefined : JSON.stringify(answer.body ?? null),
    });
  });

  return {
    unmatched,
    all: () => calls,
    calls: (key) => calls.filter((call) => call.key === key),
  };
}

// Guarda valores no localStorage antes de qualquer script da página rodar (vale para toda
// navegação e reload do teste).
export async function seedStorage(page, values) {
  await page.addInitScript((entries) => {
    for (const [key, value] of Object.entries(entries)) window.localStorage.setItem(key, value);
  }, values);
}

// Sessão logada (mesmo formato do AuthProvider).
export const SESSION_KEY = "logcoach.session";
export const session = (token = "token-e2e", email = "voce@exemplo.com") => ({
  [SESSION_KEY]: JSON.stringify({ token, email }),
});

/** Cor de fundo computada (rgb) de um seletor. */
export function backgroundOf(page, selector) {
  return page.evaluate(
    (sel) => getComputedStyle(document.querySelector(sel)).backgroundColor,
    selector,
  );
}

/** "#rrggbb" → "rgb(r, g, b)", o formato que o navegador devolve. */
export function rgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}

/**
 * Roda o axe-core na página inteira, com todas as regras (inclusive color-contrast), e devolve
 * as violações sérias e críticas já formatadas. Antes, desliga transições e animações: o axe
 * mede a cor naquele instante, e uma transição em andamento daria cor intermediária.
 */
export async function seriousViolations(page) {
  await page.addStyleTag({
    content: "*, *::before, *::after { transition: none !important; animation: none !important; }",
  });
  await page.addScriptTag({ path: AXE_PATH });
  const violations = await page.evaluate(async () => {
    const results = await window.axe.run(document);
    // Guarda contra falso verde: a regra de contraste precisa ter medido algum elemento.
    const measured = results.passes.find((rule) => rule.id === "color-contrast");
    if (!measured?.nodes.length) throw new Error("O axe não mediu nenhum contraste.");
    return results.violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => ({
        id: v.id,
        impact: v.impact,
        help: v.help,
        nodes: v.nodes.map((n) => ({
          target: n.target.join(" "),
          summary: n.any[0]?.message ?? n.failureSummary,
        })),
      }));
  });
  return violations.map(
    (v) =>
      `${v.id} (${v.impact}): ${v.help}\n` +
      v.nodes.map((n) => `  - ${n.target}: ${n.summary}`).join("\n"),
  );
}
