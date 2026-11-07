// Tema claro/escuro no navegador de verdade: o que o jsdom não consegue verificar (cor
// computada, ordem de execução dos scripts, preferência do sistema, contraste real).
import { expect, test } from "@playwright/test";
import {
  analysis,
  backgroundOf,
  happyRoutes,
  mockApi,
  REPORT_CODE,
  rgb,
  seedStorage,
  seriousViolations,
  session,
} from "./helpers.js";

const THEME_KEY = "logcoach.theme";
const BG = { light: "#fffffe", dark: "#0f0e17" };

const dataTheme = (page) => page.evaluate(() => document.documentElement.dataset.theme);
// A cor de fundo tem transição no CSS: espera chegar ao valor final em vez de ler no meio dela.
const expectBackground = (page, selector, hex) =>
  expect.poll(() => backgroundOf(page, selector)).toBe(rgb(hex));
const toggleButton = (page) => page.getByRole("button", { name: /Ativar tema/ });

test.beforeEach(async ({ page }) => {
  await mockApi(page, happyRoutes());
});

test.describe("primeira visita segue o sistema", () => {
  for (const scheme of ["light", "dark"]) {
    test.describe(`sistema ${scheme}`, () => {
      test.use({ colorScheme: scheme });

      test(`abre no tema ${scheme} com o fundo do token`, async ({ page }) => {
        await page.goto("/");
        expect(await dataTheme(page)).toBe(scheme);
        await expectBackground(page, "body", BG[scheme]);
        await expectBackground(page, "html", BG[scheme]);
        await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute(
          "content",
          BG[scheme],
        );
      });
    });
  }
});

test.describe("botão de alternar", () => {
  test.use({ colorScheme: "dark" });

  test("alterna, a escolha sobrevive ao reload e prevalece sobre o sistema", async ({ page }) => {
    await page.goto("/");
    expect(await dataTheme(page)).toBe("dark");

    await toggleButton(page).click();
    expect(await dataTheme(page)).toBe("light");
    await expectBackground(page, "body", BG.light);
    expect(await page.evaluate((k) => localStorage.getItem(k), THEME_KEY)).toBe("light");

    await page.reload();
    expect(await dataTheme(page)).toBe("light");
    await expectBackground(page, "body", BG.light);

    // Mudar o sistema agora não muda nada: a escolha da pessoa manda.
    await page.emulateMedia({ colorScheme: "light" });
    await page.emulateMedia({ colorScheme: "dark" });
    expect(await dataTheme(page)).toBe("light");

    // E volta para o escuro pelo botão, também guardado.
    await toggleButton(page).click();
    expect(await dataTheme(page)).toBe("dark");
    await page.reload();
    expect(await dataTheme(page)).toBe("dark");
  });

  test("sem escolha salva, acompanha o sistema com a página aberta", async ({ page }) => {
    await page.goto("/");
    expect(await dataTheme(page)).toBe("dark");

    await page.emulateMedia({ colorScheme: "light" });
    await expect.poll(() => dataTheme(page)).toBe("light");
    await expectBackground(page, "body", BG.light);

    await page.emulateMedia({ colorScheme: "dark" });
    await expect.poll(() => dataTheme(page)).toBe("dark");
  });

  test("o tema vale em todas as telas (a escolha não se perde ao navegar)", async ({ page }) => {
    await page.goto("/");
    await toggleButton(page).click();
    await page.getByRole("link", { name: "Planos" }).click();
    await expect(page.getByRole("heading", { name: "Escolha como quer evoluir" })).toBeVisible();
    expect(await dataTheme(page)).toBe("light");
    await expectBackground(page, "body", BG.light);
  });
});

// Pronto para medir antes do React: data-theme posto, <body> e #root no DOM e a folha de
// estilo carregada (sem ela, a cor computada ainda seria a padrão do navegador).
const themeAndCssReady = () =>
  document.documentElement.dataset.theme !== undefined &&
  document.getElementById("root") !== null &&
  [...document.querySelectorAll('link[rel="stylesheet"]')].every((link) => link.sheet);

test.describe("sem flash", () => {
  test.use({ colorScheme: "dark" });

  test("com escolha clara salva e sistema escuro, o tema já está certo antes do React", async ({
    page,
  }) => {
    await seedStorage(page, { [THEME_KEY]: "light" });
    // Segura o bundle do React: enquanto ele não chega, só o script inline do index.html
    // pôde rodar. Se o data-theme já está certo nesse momento (e a tela ainda vazia), o tema
    // não depende do React e não há piscada do escuro. Este método é mais confiável que
    // observar "domcontentloaded", porque garante que o bundle ainda não executou.
    let release;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    await page.route("**/assets/*.js", async (route) => {
      await gate;
      await route.continue();
    });

    const navigation = page.goto("/", { waitUntil: "commit" });
    await page.waitForFunction(themeAndCssReady);
    const before = await page.evaluate(() => ({
      theme: document.documentElement.dataset.theme,
      colorScheme: document.documentElement.style.colorScheme,
      rootEmpty: document.getElementById("root")?.childElementCount === 0,
      background: getComputedStyle(document.body).backgroundColor,
    }));
    expect(before.rootEmpty).toBe(true); // o React ainda não montou nada
    expect(before.theme).toBe("light");
    expect(before.colorScheme).toBe("light");
    expect(before.background).toBe(rgb(BG.light));

    release();
    await navigation;
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await dataTheme(page)).toBe("light");
  });

  test("sem escolha salva, o script inline usa o sistema antes do React", async ({ page }) => {
    let release;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    await page.route("**/assets/*.js", async (route) => {
      await gate;
      await route.continue();
    });
    const navigation = page.goto("/", { waitUntil: "commit" });
    await page.waitForFunction(themeAndCssReady);
    expect(await page.evaluate(() => document.getElementById("root").childElementCount)).toBe(0);
    expect(await dataTheme(page)).toBe("dark");
    expect(await backgroundOf(page, "body")).toBe(rgb(BG.dark));
    release();
    await navigation;
  });
});

test.describe("localStorage bloqueado", () => {
  test.use({ colorScheme: "dark" });

  test("o site abre e o tema alterna durante a sessão", async ({ page }) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.addInitScript(() => {
      const fail = () => {
        throw new DOMException("bloqueado", "SecurityError");
      };
      Storage.prototype.getItem = fail;
      Storage.prototype.setItem = fail;
      Storage.prototype.removeItem = fail;
    });

    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await dataTheme(page)).toBe("dark");

    await toggleButton(page).click();
    expect(await dataTheme(page)).toBe("light");
    await expectBackground(page, "body", BG.light);
    await toggleButton(page).click();
    expect(await dataTheme(page)).toBe("dark");
    expect(errors).toEqual([]);
  });
});

test.describe("celular 360×740", () => {
  test.use({ viewport: { width: 360, height: 740 } });

  for (const theme of ["light", "dark"]) {
    test(`o cabeçalho não gera rolagem horizontal (${theme})`, async ({ page }) => {
      await seedStorage(page, { [THEME_KEY]: theme, ...session() });
      await mockApi(page, { ...happyRoutes(), "GET /me": { body: { email: "voce@exemplo.com" } } });
      for (const path of ["/", "/planos", "/entrar?modo=login"]) {
        await page.goto(`/#${path}`);
        await expect(toggleButton(page)).toBeVisible();
        const sizes = await page.evaluate(() => ({
          scroll: document.documentElement.scrollWidth,
          client: document.documentElement.clientWidth,
        }));
        expect(sizes.scroll, `${path} em ${theme}`).toBeLessThanOrEqual(sizes.client);
      }
    });
  }
});

// ---------- contraste real (axe-core com color-contrast ligado) ----------

const SCREENS = {
  início: { path: "/", ready: (page) => page.getByRole("heading", { level: 1 }) },
  login: { path: "/entrar?modo=login", ready: (page) => page.getByLabel("E-mail") },
  cadastro: { path: "/entrar?modo=cadastro", ready: (page) => page.getByLabel("E-mail") },
  planos: {
    path: "/planos",
    ready: (page) => page.getByRole("heading", { name: "Escolha como quer evoluir" }),
  },
  "escolher luta": {
    path: `/relatorio/${REPORT_CODE}`,
    ready: (page) => page.getByRole("heading", { name: "1. Escolha a luta" }),
    async prepare(page) {
      await page.getByRole("button", { name: /Nek'zali.*luta 34/ }).click();
      await expect(page.getByText("Harmonist")).toBeVisible();
    },
  },
  resultado: {
    path: "/analise/7dbcd6251c8c4000818a61ea67785e36",
    ready: (page) => page.getByRole("heading", { level: 1 }),
    async prepare(page) {
      await page.locator(".compared > summary").click();
    },
  },
  "resultado com nomes à mostra": {
    path: "/analise/7dbcd6251c8c4000818a61ea67785e36",
    names: true,
    ready: (page) => page.getByRole("heading", { level: 1 }),
    async prepare(page) {
      await page.locator(".compared > summary").click();
      await page.getByRole("button", { name: "Mostrar nomes" }).click();
      await expect(page.getByRole("button", { name: "Mostrar nomes" })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
    },
  },
};

test.describe("contraste e acessibilidade no navegador", () => {
  for (const theme of ["light", "dark"]) {
    for (const [name, screen] of Object.entries(SCREENS)) {
      test(`${name} (${theme}): sem violações sérias`, async ({ page }) => {
        const result = analysis();
        if (screen.names) {
          // Nomes reais fictícios só para exercitar o texto dos nomes visíveis.
          result.result.comparison.players.forEach((player, i) => {
            player.name = `Jogador${i + 1}`;
            player.server = "Servidor";
          });
        }
        await seedStorage(page, { [THEME_KEY]: theme });
        await mockApi(page, { ...happyRoutes(), [`GET /analyses/${result.id}`]: { body: result } });

        await page.goto(`/#${screen.path}`);
        await expect(screen.ready(page)).toBeVisible();
        if (screen.prepare) await screen.prepare(page);
        expect(await dataTheme(page)).toBe(theme);

        expect(await seriousViolations(page)).toEqual([]);
      });
    }
  }
});
