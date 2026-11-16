// Tela inicial (landing) no navegador de verdade: primeira dobra, rolagem horizontal,
// acessibilidade com contraste, teclado e foco, movimento reduzido e rede. O que o jsdom não
// mede (layout, cor computada, animações) fica aqui; o conteúdo está em Home.test.jsx.
import { expect, test } from "@playwright/test";
import {
  happyRoutes,
  mockApi,
  REPORT_CODE,
  REPORT_LINK,
  seedStorage,
  seriousViolations,
} from "./helpers.js";

const THEME_KEY = "logcoach.theme";
const THEMES = ["dark", "light"];
const DESKTOP = { width: 1440, height: 800 };
const SIZES = [{ width: 375, height: 812 }, { width: 768, height: 1024 }, DESKTOP];

const campo = (page) => page.getByLabel("Link do relatório no Warcraft Logs");
const analisar = (page) => page.getByRole("button", { name: "Analisar" });
const h1 = (page) =>
  page.getByRole("heading", { level: 1, name: "Descubra os erros que mais custam seu dano" });

async function openLanding(page, theme) {
  await seedStorage(page, { [THEME_KEY]: theme });
  await mockApi(page, happyRoutes());
  await page.goto("/");
  await expect(h1(page)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe(theme);
}

/** Retângulo do elemento na viewport (sem rolar a página). */
const rectOf = (locator) =>
  locator.evaluate((el) => {
    const r = el.getBoundingClientRect();
    return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width };
  });

test.describe("V5: primeira dobra em 1440×800", () => {
  test.use({ viewport: DESKTOP });

  for (const theme of THEMES) {
    test(`título, campo e "Analisar" sem rolar; fundo do hero pelo token (${theme})`, async ({
      page,
    }) => {
      await openLanding(page, theme);
      expect(await page.evaluate(() => window.scrollY)).toBe(0);

      for (const [name, locator] of [
        ["título", h1(page)],
        ["campo", campo(page)],
        ["Analisar", analisar(page)],
      ]) {
        const r = await rectOf(locator);
        expect(r.top, `${name}: topo`).toBeGreaterThanOrEqual(0);
        expect(r.bottom, `${name}: base`).toBeLessThanOrEqual(DESKTOP.height);
        expect(r.left, `${name}: esquerda`).toBeGreaterThanOrEqual(0);
        expect(r.right, `${name}: direita`).toBeLessThanOrEqual(DESKTOP.width);
      }

      // O hero ocupa a primeira dobra inteira, de ponta a ponta.
      const hero = await rectOf(page.locator(".hero"));
      expect(hero.top).toBeLessThanOrEqual(0);
      expect(hero.width).toBe(DESKTOP.width);
      expect(hero.bottom).toBeGreaterThanOrEqual(DESKTOP.height);

      const colors = await page.evaluate(() => {
        const probe = document.createElement("div");
        probe.style.backgroundColor = "var(--hero-bg)";
        document.body.append(probe);
        const token = getComputedStyle(probe).backgroundColor;
        probe.remove();
        return {
          token,
          hero: getComputedStyle(document.querySelector(".hero")).backgroundColor,
          body: getComputedStyle(document.body).backgroundColor,
        };
      });
      expect(colors.hero).toBe(colors.token);
      expect(colors.hero).not.toBe(colors.body);
    });
  }
});

test.describe("V6: sem rolagem horizontal", () => {
  for (const size of SIZES) {
    test.describe(`${size.width}×${size.height}`, () => {
      test.use({ viewport: size });

      for (const theme of THEMES) {
        test(`landing (${theme})`, async ({ page }) => {
          await openLanding(page, theme);
          const sizes = await page.evaluate(() => ({
            scroll: document.documentElement.scrollWidth,
            client: document.documentElement.clientWidth,
          }));
          expect(sizes.scroll).toBeLessThanOrEqual(sizes.client);

          // Barra do link com largura útil e o convite sem cobrir o campo.
          const field = await rectOf(campo(page));
          expect(field.width).toBeGreaterThanOrEqual(280);
          const cta = page.getByRole("link", { name: "Criar conta grátis" });
          const c = await rectOf(cta);
          const overlaps =
            c.left < field.right &&
            c.right > field.left &&
            c.top < field.bottom &&
            c.bottom > field.top;
          expect(overlaps, "o convite cobre o campo").toBe(false);
          const hit = await campo(page).evaluate((el) => {
            const r = el.getBoundingClientRect();
            return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === el;
          });
          expect(hit, "o meio do campo é clicável").toBe(true);
        });
      }
    });
  }
});

test.describe("V7: acessibilidade com contraste (axe)", () => {
  for (const size of [{ width: 375, height: 812 }, DESKTOP]) {
    test.describe(`${size.width}px`, () => {
      test.use({ viewport: size });

      for (const theme of THEMES) {
        test(`sem violações sérias (${theme})`, async ({ page }) => {
          await openLanding(page, theme);
          expect(await seriousViolations(page)).toEqual([]);
        });

        test(`sem violações sérias com o erro do campo à mostra (${theme})`, async ({ page }) => {
          await openLanding(page, theme);
          await analisar(page).click();
          await expect(page.getByText("Cole o link do seu log do Warcraft Logs.")).toBeVisible();
          expect(await seriousViolations(page)).toEqual([]);
        });
      }
    });
  }
});

test.describe("V8: teclado e foco", () => {
  test.use({ viewport: DESKTOP });

  for (const theme of THEMES) {
    test(`Tab do topo chega ao campo e depois ao "Analisar", com foco visível (${theme})`, async ({
      page,
    }) => {
      await openLanding(page, theme);
      const visited = [];
      let reached = false;
      for (let i = 0; i < 20 && !reached; i++) {
        await page.keyboard.press("Tab");
        const info = await page.evaluate(() => {
          const el = document.activeElement;
          const style = getComputedStyle(el);
          return {
            id: el.id,
            name: el.getAttribute("aria-label") ?? el.textContent.trim(),
            outline: style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0,
            shadow: style.boxShadow !== "none",
          };
        });
        visited.push(info);
        reached = info.id === "link";
      }
      expect(reached, `ordem: ${visited.map((v) => v.name || v.id).join(" → ")}`).toBe(true);
      // O primeiro Tab cai no topo da página (pular para o conteúdo), não no meio do hero.
      expect(visited[0].name).toBe("Pular para o conteúdo");

      await page.keyboard.press("Tab");
      await expect(analisar(page)).toBeFocused();
      visited.push(
        await page.evaluate(() => {
          const style = getComputedStyle(document.activeElement);
          return {
            name: "Analisar",
            outline: style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0,
            shadow: style.boxShadow !== "none",
          };
        }),
      );
      for (const v of visited) {
        expect(v.outline || v.shadow, `foco visível em ${v.name || v.id}`).toBe(true);
      }
    });
  }

  test("Enter no campo com link válido abre a escolha da luta", async ({ page }) => {
    await openLanding(page, "dark");
    await campo(page).fill(REPORT_LINK);
    await campo(page).press("Enter");
    await expect(page).toHaveURL(new RegExp(`#/relatorio/${REPORT_CODE}$`));
  });
});

test.describe("V9: movimento reduzido", () => {
  test.use({ viewport: DESKTOP });

  test("com reduce, nenhuma animação na landing", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openLanding(page, "dark");
    expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
  });

  test("sem preferência, a landing anima (a verificação acima não passa à toa)", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await openLanding(page, "dark");
    expect(await page.evaluate(() => document.getAnimations().length)).toBeGreaterThan(0);
  });
});

test.describe("V10: rede", () => {
  test.use({ viewport: DESKTOP });

  for (const theme of THEMES) {
    test(`nenhum pedido para fora de localhost e api.test (${theme})`, async ({ page }) => {
      const hosts = [];
      page.on("request", (request) => {
        const url = new URL(request.url());
        if (url.protocol === "data:" || url.protocol === "blob:") return;
        hosts.push(url.hostname);
      });
      await openLanding(page, theme);
      await page.getByRole("button", { name: "Usar o log de exemplo" }).click();
      await page.mouse.wheel(0, 2000);
      await page.waitForLoadState("networkidle");
      expect(hosts.length).toBeGreaterThan(0);
      expect([...new Set(hosts)].filter((h) => h !== "localhost" && h !== "api.test")).toEqual([]);
    });
  }
});

test.describe("V12: outras telas sem cabeçalho por cima", () => {
  for (const size of [{ width: 375, height: 812 }, DESKTOP]) {
    test.describe(`${size.width}px`, () => {
      test.use({ viewport: size });

      for (const path of ["/planos", "/entrar?modo=login"]) {
        test(`${path}: o conteúdo começa abaixo do cabeçalho`, async ({ page }) => {
          await mockApi(page, happyRoutes());
          await page.goto(`/#${path}`);
          await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
          const header = await rectOf(page.locator("header.topbar"));
          const main = await rectOf(page.locator("main"));
          expect(main.top).toBeGreaterThanOrEqual(header.bottom);
          expect(
            await page.locator("header.topbar").evaluate((el) => getComputedStyle(el).position),
          ).not.toBe("absolute");
        });
      }
    });
  }
});
