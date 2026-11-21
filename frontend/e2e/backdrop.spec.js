// Cenário: Silvermoon de dia no tema claro e Suramar à noite no escuro, fixo atrás de todas as
// telas (components/Backdrop.jsx). Confere o que o jsdom não vê: a imagem certa por tema, a
// cidade desfocada nas telas de uso, a outra cidade baixada só depois, a troca de tema e o
// contraste do texto sobre a imagem.
import { expect, test } from "@playwright/test";
import { measureTextContrast, waitForBackdrop } from "./contrast.js";
import { analysis, happyRoutes, mockApi, REPORT_CODE, seedStorage } from "./helpers.js";

const THEME_KEY = "logcoach.theme";
const CENARIO = '[data-testid="cenario"]';
const CITY = { light: "silvermoon", dark: "suramar" };
const OTHER = { light: "dark", dark: "light" };
const SCREENS = {
  inicio: { path: "/", mode: "pleno" },
  login: { path: "/entrar?modo=login", mode: "pleno" },
  luta: { path: `/relatorio/${REPORT_CODE}`, mode: "fundo" },
  resultado: { path: `/analise/${analysis().id}`, mode: "fundo" },
  planos: { path: "/planos", mode: "fundo" },
};
const SIZES = { desktop: { width: 1440, height: 900 }, celular: { width: 375, height: 812 } };

async function open(page, path, theme) {
  await seedStorage(page, { [THEME_KEY]: theme });
  await mockApi(page, happyRoutes());
  await page.goto(`/#${path}`);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
}

/** Cidade visível agora e o modo do cenário. */
const backdropState = (page) =>
  page.evaluate((sel) => {
    const el = document.querySelectorAll(sel);
    const shown = [...el[0].querySelectorAll(".backdrop-city")].filter(
      (pic) => getComputedStyle(pic).display !== "none",
    );
    const img = shown[0]?.querySelector("img");
    const r = el[0].getBoundingClientRect();
    return {
      count: el.length,
      hidden: el[0].getAttribute("aria-hidden"),
      position: getComputedStyle(el[0]).position,
      pointer: getComputedStyle(el[0]).pointerEvents,
      fills:
        r.left === 0 &&
        r.top === 0 &&
        r.width === document.documentElement.clientWidth &&
        r.height === innerHeight,
      mode: el[0].dataset.cenario,
      shown: shown.length,
      src: img?.currentSrc ?? "",
      filter: img ? getComputedStyle(img).filter : "",
    };
  }, CENARIO);

for (const theme of ["dark", "light"]) {
  test.describe(`tema ${theme}`, () => {
    for (const [name, { path, mode }] of Object.entries(SCREENS)) {
      test(`${name}: uma cidade (${CITY[theme]}), fixa e decorativa, modo ${mode}`, async ({
        page,
      }) => {
        await open(page, path, theme);
        await waitForBackdrop(page);
        const s = await backdropState(page);
        expect(s).toMatchObject({
          count: 1,
          hidden: "true",
          position: "fixed",
          pointer: "none",
          fills: true,
          mode,
          shown: 1,
        });
        expect(s.src).toContain(`/cenario/${CITY[theme]}-`);
        // Telas de uso: desfocada. Início e login: nítida.
        if (mode === "fundo") expect(s.filter).toContain("blur");
        else expect(s.filter).toBe("none");
      });
    }

    for (const [size, viewport] of Object.entries(SIZES)) {
      test.describe(size, () => {
        test.use({ viewport });
        for (const [name, { path }] of Object.entries(SCREENS)) {
          test(`${name}: texto AA sobre a cidade`, async ({ page }) => {
            // Cada medida desenha a tela duas vezes e lê os pixels: mais lento que o normal.
            test.slow();
            await open(page, path, theme);
            // O início é a tela em que a cidade aparece inteira e o véu sobe com a rolagem:
            // mede no topo, no meio do caminho e com o véu completo.
            const steps = name === "inicio" ? [0, 350, 700] : [0];
            for (const y of steps) {
              const bad = await measureTextContrast(page, y);
              expect(bad, `rolagem ${y}px`).toEqual([]);
            }
          });
        }
      });
    }

    test("a outra cidade é baixada em segundo plano, e a troca de tema mostra a outra", async ({
      page,
    }) => {
      const cities = new Set();
      page.on("request", (req) => {
        const m = /\/cenario\/(\w+)-/.exec(req.url());
        if (m) cities.add(m[1]);
      });
      await open(page, "/", theme);
      await waitForBackdrop(page);
      // A outra cidade vem em segundo plano, depois que a página carregou.
      await expect.poll(() => cities.has(CITY[OTHER[theme]]), { timeout: 10_000 }).toBe(true);
      expect(cities.has(CITY[theme])).toBe(true);

      await page.getByRole("button", { name: /Ativar tema/ }).click();
      await waitForBackdrop(page);
      expect((await backdropState(page)).src).toContain(`/cenario/${CITY[OTHER[theme]]}-`);
    });
  });
}

test.describe("celular em pé", () => {
  test.use({ viewport: SIZES.celular });
  test("usa o corte vertical da cidade", async ({ page }) => {
    await open(page, "/", "dark");
    await waitForBackdrop(page);
    expect((await backdropState(page)).src).toContain("/cenario/suramar-celular.webp");
  });
});

test.describe("sem movimento", () => {
  test.use({ reducedMotion: "reduce" });
  test("a troca de tema não tem fade", async ({ page }) => {
    await open(page, "/", "dark");
    await waitForBackdrop(page);
    const transition = await page.evaluate(
      () => getComputedStyle(document.querySelector(".backdrop-city")).transitionDuration,
    );
    expect(transition).toBe("0s");
  });
});
