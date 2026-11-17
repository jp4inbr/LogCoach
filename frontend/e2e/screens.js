// Telas da repaginação (fases 2 e 3), compartilhadas entre screens.spec.js e
// backdrop.spec.js: rota, título, dados simulados e como deixar cada uma pronta.
import { expect } from "@playwright/test";
import {
  analysis,
  apiError,
  happyRoutes,
  mockApi,
  REPORT_CODE,
  seedStorage,
  session,
} from "./helpers.js";

export const THEME_KEY = "logcoach.theme";
export const THEMES = ["dark", "light"];
export const SIZES = [
  { width: 375, height: 812 },
  { width: 768, height: 1024 },
  { width: 1440, height: 800 },
];
export const ANALYSIS_ID = analysis().id;

export const ME = {
  email: "voce@exemplo.com",
  created_at: "2026-10-01T12:00:00Z",
  plan: "gratis",
  analyses_this_month: 3,
  monthly_limit: 5,
};

// Histórico com o jogador de exemplo (pseudônimo) e dois chefes, para o gráfico de evolução.
function historyItem(id, day, dps, gap, boss = "Nek'zali, a Enrosca-almas") {
  return {
    id,
    created_at: `2026-11-${day}T15:00:00Z`,
    report_code: REPORT_CODE,
    fight_id: 34,
    player_name: "Harmonist",
    boss,
    difficulty: "Mítico",
    dps,
    dps_gap_pct: gap,
    mistakes_count: 4,
  };
}
export const HISTORY = [
  historyItem("a3", "06", 240000, -9.5),
  historyItem("a2", "03", 225680.6, -15.2),
  historyItem("a1", "01", 1_180_000, 3.1),
];

export const h1 = (page) => page.getByRole("heading", { level: 1 });

/**
 * Telas da fase 2. `h1`: nome acessível do título (inalterado); null = a tela não tem h1
 * (estado de erro, decisão conservadora: nada de título novo). `current`: link do cabeçalho
 * com aria-current. `internal`: tela interna (cabeçalho acima do conteúdo, faixa-título).
 */
export const SCREENS = {
  inicial: {
    path: "/",
    h1: "Descubra os erros que mais custam seu dano",
    current: "Analisar",
    internal: false,
  },
  entrar: {
    path: "/entrar?modo=login",
    h1: "Entre na sua conta",
    current: null,
    internal: true,
    ready: (page) => page.getByLabel("E-mail"),
  },
  cadastro: {
    path: "/entrar?modo=cadastro",
    h1: "Crie sua conta grátis",
    current: null,
    internal: true,
    ready: (page) => page.getByLabel("E-mail"),
  },
  "escolher luta com lista": {
    path: `/relatorio/${REPORT_CODE}`,
    h1: "The Venomous Abyss — Mítico",
    current: null,
    internal: true,
    ready: (page) => page.getByRole("heading", { name: "1. Escolha a luta" }),
    async prepare(page) {
      await page.getByRole("button", { name: /Nek'zali.*luta 34/ }).click();
      await expect(page.getByText("Harmonist")).toBeVisible();
    },
  },
  "escolher luta com erro": {
    path: `/relatorio/${REPORT_CODE}`,
    h1: null,
    current: null,
    internal: true,
    routes: {
      "POST /reports/resolve": apiError(
        503,
        "wcl_unavailable",
        "O Warcraft Logs não respondeu agora. Tente de novo em alguns minutos.",
      ),
    },
    ready: (page) => page.getByText("Não deu para abrir esse relatório"),
  },
  resultado: {
    path: `/analise/${ANALYSIS_ID}`,
    h1: "Nek'zali, a Enrosca-almas",
    current: null,
    internal: true,
    async prepare(page) {
      await page.locator(".compared > summary").click();
    },
  },
  "resultado com nomes à mostra": {
    path: `/analise/${ANALYSIS_ID}`,
    h1: "Nek'zali, a Enrosca-almas",
    names: true,
    current: null,
    internal: true,
    async prepare(page) {
      await page.locator(".compared > summary").click();
      await page.getByRole("button", { name: "Mostrar nomes" }).click();
      await expect(page.getByRole("button", { name: "Mostrar nomes" })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
    },
  },
  "perfil com análises": {
    path: "/perfil",
    h1: "Seu perfil",
    current: "Perfil",
    internal: true,
    logged: true,
    routes: { "GET /me": { body: ME }, "GET /me/analyses": { body: HISTORY } },
  },
  "perfil sem análises": {
    path: "/perfil",
    h1: "Seu perfil",
    current: "Perfil",
    internal: true,
    logged: true,
    routes: { "GET /me": { body: ME }, "GET /me/analyses": { body: [] } },
  },
  planos: {
    path: "/planos",
    h1: "Escolha como quer evoluir",
    current: "Planos",
    internal: true,
  },
};

/** Abre a tela no tema pedido, com a API simulada, e espera ela ficar pronta. */
export async function openScreen(page, name, theme) {
  const screen = SCREENS[name];
  const result = analysis();
  if (screen.names) {
    result.result.comparison.players.forEach((player, i) => {
      player.name = `Jogador${i + 1}`;
      player.server = "Servidor";
    });
  }
  await seedStorage(page, { [THEME_KEY]: theme, ...(screen.logged ? session() : {}) });
  const api = await mockApi(page, {
    ...happyRoutes(),
    [`GET /analyses/${result.id}`]: { body: result },
    "GET /me": { body: ME },
    ...screen.routes,
  });
  await page.goto(`/#${screen.path}`);
  if (screen.ready) await expect(screen.ready(page)).toBeVisible();
  else await expect(h1(page)).toBeVisible();
  if (screen.prepare) await screen.prepare(page);
  expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe(theme);
  return api;
}

/** Valor computado de um token de cor (rgb), medido num elemento de prova. */
export const tokenColor = (page, token) =>
  page.evaluate((name) => {
    const probe = document.createElement("div");
    probe.style.color = `var(${name})`;
    document.body.append(probe);
    const value = getComputedStyle(probe).color;
    probe.remove();
    return value;
  }, token);
