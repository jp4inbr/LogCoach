// Fase 3: o cenário da tela inicial (fundo do hero + placa "LogCoach" gravada) atrás de
// todas as telas, fixo na viewport. X7 (axe) é o W3 e X9 (rolagem lateral) é o W4, ambos em
// screens.spec.js, que roda as mesmas 11 telas nos dois temas.
import { expect, test } from "@playwright/test";
import { analysis, happyRoutes, mockApi, seedStorage } from "./helpers.js";
import { openScreen, SCREENS, THEME_KEY, THEMES } from "./screens.js";

const PHONE = { width: 375, height: 812 };
const DESKTOP = { width: 1440, height: 800 };
const CENARIO = '[data-testid="cenario"]';

/** Caixa do cenário e estilos que importam (X1, X3). */
const backdropInfo = (page) =>
  page.evaluate((sel) => {
    const all = document.querySelectorAll(sel);
    const el = all[0];
    if (!el) return { count: 0 };
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return {
      count: all.length,
      hidden: el.getAttribute("aria-hidden"),
      position: s.position,
      pointer: s.pointerEvents,
      rect: [r.left, r.top, r.width, r.height].map(Math.round),
      viewport: [0, 0, document.documentElement.clientWidth, window.innerHeight],
    };
  }, CENARIO);

test.describe("X1: um só cenário, decorativo e do tamanho da viewport", () => {
  for (const size of [PHONE, DESKTOP]) {
    test.describe(`${size.width}px`, () => {
      test.use({ viewport: size });
      for (const theme of THEMES) {
        for (const name of Object.keys(SCREENS)) {
          test(`${name} (${theme})`, async ({ page }) => {
            await openScreen(page, name, theme);
            const info = await backdropInfo(page);
            expect(info.count).toBe(1);
            expect(info.hidden).toBe("true");
            expect(info.position).toBe("fixed");
            expect(info.pointer).toBe("none");
            expect(info.rect).toEqual(info.viewport);
          });
        }
      }
    });
  }
});

/**
 * Do topo para baixo, tudo o que está no ponto antes do cenário precisa ser transparente
 * (sem cor nem imagem de fundo): o cenário é o que aparece ali. Para o hit-test enxergar o
 * cenário, ele recebe pointer-events só durante a medida.
 */
async function layersAbove(page, x, y) {
  return page.evaluate(
    ([px, py, sel]) => {
      const style = document.createElement("style");
      style.textContent = `${sel}, ${sel} * { pointer-events: auto !important; }`;
      document.head.append(style);
      const stack = document.elementsFromPoint(px, py);
      style.remove();
      const backdrop = document.querySelector(sel);
      const above = [];
      let reached = false;
      for (const el of stack) {
        if (backdrop.contains(el)) {
          reached = true;
          break;
        }
        const s = getComputedStyle(el);
        above.push({
          el: `${el.tagName.toLowerCase()}.${[...el.classList].join(".")}`,
          solid: s.backgroundColor !== "rgba(0, 0, 0, 0)" || s.backgroundImage !== "none",
        });
      }
      return { reached, above };
    },
    [x, y, CENARIO],
  );
}

test.describe("X2: o cenário aparece atrás do conteúdo", () => {
  for (const size of [PHONE, DESKTOP]) {
    test.describe(`${size.width}px`, () => {
      test.use({ viewport: size });
      for (const theme of THEMES) {
        for (const name of Object.keys(SCREENS)) {
          test(`${name} (${theme})`, async ({ page }) => {
            await openScreen(page, name, theme);
            // Margem esquerda, no meio da altura: fora de cartões e do cabeçalho.
            const result = await layersAbove(page, 3, Math.round(size.height / 2));
            expect(result.reached, "o cenário não está no ponto").toBe(true);
            const solid = result.above.filter((layer) => layer.solid).map((layer) => layer.el);
            expect(solid, "camadas com fundo sólido por cima do cenário").toEqual([]);
          });
        }
      }
    });
  }
});

test.describe("X3: o cenário fica fixo ao rolar", () => {
  test.use({ viewport: DESKTOP });
  for (const theme of THEMES) {
    test(`resultado rolado até o fim (${theme})`, async ({ page }) => {
      await openScreen(page, "resultado", theme);
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(500);
      const info = await backdropInfo(page);
      expect(info.rect).toEqual(info.viewport);
      const result = await layersAbove(page, 3, DESKTOP.height - 20);
      expect(result.reached).toBe(true);
    });
  }
});

/** Screenshot só do cenário: todo o resto fica invisível (sem tirar do layout). */
async function backdropShot(page) {
  await page.addStyleTag({
    content: `body * { visibility: hidden !important; }
      ${CENARIO}, ${CENARIO} * { visibility: visible !important; }`,
  });
  return page.screenshot();
}

test.describe("X4: o cenário das telas internas é o mesmo da tela inicial", () => {
  test.use({ viewport: DESKTOP, reducedMotion: "reduce" });
  for (const theme of THEMES) {
    test(`inicial × planos × resultado (${theme})`, async ({ page }) => {
      const shots = {};
      const classes = {};
      for (const name of ["inicial", "planos", "resultado"]) {
        await openScreen(page, name, theme);
        classes[name] = await page.locator(CENARIO).getAttribute("class");
        shots[name] = (await backdropShot(page)).toString("base64");
      }
      expect(classes.planos).toBe(classes.inicial);
      expect(classes.resultado).toBe(classes.inicial);
      // Diferença de pixels medida no próprio navegador (canvas), com tolerância de 1%.
      for (const other of ["planos", "resultado"]) {
        const diff = await page.evaluate(
          async ([a, b]) => {
            const load = (data) =>
              new Promise((resolve) => {
                const img = new Image();
                img.onload = () => resolve(img);
                img.src = `data:image/png;base64,${data}`;
              });
            const [ia, ib] = await Promise.all([load(a), load(b)]);
            const read = (img) => {
              const canvas = document.createElement("canvas");
              canvas.width = img.width;
              canvas.height = img.height;
              const ctx = canvas.getContext("2d");
              ctx.drawImage(img, 0, 0);
              return ctx.getImageData(0, 0, img.width, img.height).data;
            };
            const [da, db] = [read(ia), read(ib)];
            let differ = 0;
            for (let i = 0; i < da.length; i += 4) {
              const delta =
                Math.abs(da[i] - db[i]) +
                Math.abs(da[i + 1] - db[i + 1]) +
                Math.abs(da[i + 2] - db[i + 2]);
              if (delta > 6) differ++;
            }
            return {
              same: ia.width === ib.width && ia.height === ib.height,
              ratio: differ / (da.length / 4),
            };
          },
          [shots.inicial, shots[other]],
        );
        expect(diff.same).toBe(true);
        expect(
          diff.ratio,
          `inicial × ${other}: ${(diff.ratio * 100).toFixed(2)}% diferente`,
        ).toBeLessThanOrEqual(0.01);
      }
    });
  }
});

test.describe("X5: a faixa-título não tem fundo nem placa próprios", () => {
  test.use({ viewport: DESKTOP });
  for (const theme of THEMES) {
    for (const [name, screen] of Object.entries(SCREENS)) {
      if (!screen.internal || screen.h1 === null) continue;
      test(`${name} (${theme})`, async ({ page }) => {
        await openScreen(page, name, theme);
        const band = await page.locator("main .page-band").evaluate((el) => {
          const s = getComputedStyle(el);
          const after = getComputedStyle(el, "::after");
          const before = getComputedStyle(el, "::before");
          return {
            background: s.backgroundColor,
            image: s.backgroundImage,
            shadow: s.boxShadow,
            pseudo: [after.content, before.content],
            decor: el.querySelectorAll('[aria-hidden="true"], [class*="slab"], [class*="backdrop"]')
              .length,
          };
        });
        expect(band.background).toBe("rgba(0, 0, 0, 0)");
        expect(band.image).toBe("none");
        expect(band.shadow).toBe("none");
        expect(band.pseudo).toEqual(["none", "none"]);
        expect(band.decor).toBe(0);
        // O cabeçalho também não pinta fundo por cima do cenário (como na tela inicial).
        const header = await page.locator("header.topbar").evaluate((el) => {
          const s = getComputedStyle(el);
          return [s.backgroundColor, s.backgroundImage, s.boxShadow];
        });
        expect(header).toEqual(["rgba(0, 0, 0, 0)", "none", "none"]);
      });
    }
  }
});

test.describe("X8: animação do cenário só sem pedido de menos movimento", () => {
  test.use({ viewport: DESKTOP });
  for (const name of ["planos", "resultado", "perfil com análises"]) {
    test(`${name}: com reduce nada anima; sem preferência, o cenário anima`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await openScreen(page, name, "dark");
      expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);

      await page.emulateMedia({ reducedMotion: "no-preference" });
      await expect
        .poll(() =>
          page.evaluate(
            (sel) =>
              document
                .getAnimations()
                .filter((a) => document.querySelector(sel).contains(a.effect?.target)).length,
            CENARIO,
          ),
        )
        .toBeGreaterThan(0);
    });
  }
});

test.describe("X8b: a tela inicial continua com o mesmo cenário depois de navegar", () => {
  test.use({ viewport: DESKTOP });
  test("inicial → planos → inicial: sempre um cenário", async ({ page }) => {
    await seedStorage(page, { [THEME_KEY]: "dark" });
    const result = analysis();
    await mockApi(page, { ...happyRoutes(), [`GET /analyses/${result.id}`]: { body: result } });
    await page.goto("/");
    await expect(page.locator(CENARIO)).toHaveCount(1);
    await page.getByRole("link", { name: "Planos" }).click();
    await expect(page.getByRole("heading", { name: "Escolha como quer evoluir" })).toBeVisible();
    await expect(page.locator(CENARIO)).toHaveCount(1);
    await page.getByRole("link", { name: "Analisar" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.locator(CENARIO)).toHaveCount(1);
  });
});
