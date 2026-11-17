// O visual da luz quente no navegador de verdade: a fonte carregou, o trilho dos erros funciona
// e a luz usa os tokens de cor (o jsdom não calcula estilo nem carrega fonte).
import { expect, test } from "@playwright/test";
import { analysis, happyRoutes, mockApi, seedStorage } from "./helpers.js";

const THEME_KEY = "logcoach.theme";
const RESULT = "/analise/7dbcd6251c8c4000818a61ea67785e36";
const FAMILY = "Archivo Variable";

async function open(page, path, theme = "dark") {
  await seedStorage(page, { [THEME_KEY]: theme });
  const result = analysis();
  await mockApi(page, { ...happyRoutes(), [`GET /analyses/${result.id}`]: { body: result } });
  await page.goto(`/#${path}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
}

test.describe("fonte", () => {
  test("a Archivo auto-hospedada carrega e é a fonte do título", async ({ page }) => {
    const fontRequests = [];
    page.on("request", (request) => {
      if (request.resourceType() === "font") fontRequests.push(new URL(request.url()));
    });
    await open(page, "/");
    const state = await page.evaluate(async (family) => {
      await document.fonts.ready;
      return {
        check: document.fonts.check(`700 16px "${family}"`),
        loaded: [...document.fonts].some(
          (face) => face.family.replaceAll('"', "") === family && face.status === "loaded",
        ),
        h1: getComputedStyle(document.querySelector("h1")).fontFamily,
      };
    }, FAMILY);
    expect(state.check).toBe(true);
    expect(state.loaded).toBe(true);
    expect(state.h1.startsWith(`"${FAMILY}"`)).toBe(true);
    // Auto-hospedada: a fonte vem do próprio site, nunca de um CDN.
    expect(fontRequests.length).toBeGreaterThan(0);
    for (const url of fontRequests) expect(url.host).toBe(new URL(page.url()).host);
  });
});

test.describe("luz", () => {
  for (const theme of ["dark", "light"]) {
    test(`a luz do resultado usa --glow-1 e --glow-2 (${theme})`, async ({ page }) => {
      await open(page, RESULT, theme);
      const light = await page.evaluate(() => {
        // Cor de um token como o navegador a calcula (mesmo formato do degradê computado).
        const resolve = (token) => {
          const probe = document.createElement("span");
          probe.style.color = `var(${token})`;
          document.body.append(probe);
          const value = getComputedStyle(probe).color;
          probe.remove();
          return value;
        };
        const lit = document.querySelectorAll(".lit");
        return {
          count: lit.length,
          image: lit.length ? getComputedStyle(lit[0], "::before").backgroundImage : "",
          glow1: resolve("--glow-1"),
          glow2: resolve("--glow-2"),
          body: getComputedStyle(document.body).backgroundColor,
          bg: resolve("--bg"),
        };
      });
      // Uma fonte de luz por tela, presa à diferença para os tops.
      expect(light.count).toBe(1);
      await expect(page.getByLabel("De onde vem a diferença para os tops")).toHaveClass(/\blit\b/);
      expect(light.image).toContain("radial-gradient");
      expect(light.image).toContain(light.glow1);
      expect(light.image).toContain(light.glow2);
      // O fundo da página continua sendo só o token de fundo.
      expect(light.body).toBe(light.bg);
    });
  }
});

test.describe("trilho dos erros", () => {
  test.describe("1280 px", () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test("um link por erro, na ordem dos cartões; o link 2 leva ao cartão 2", async ({ page }) => {
      await open(page, RESULT);
      const rail = page.getByRole("navigation", { name: "Erros por custo" });
      await expect(rail).toBeVisible();
      const cards = page.locator("article[id^='erro-']");
      const links = rail.getByRole("link");
      const count = await cards.count();
      expect(count).toBeGreaterThanOrEqual(2);
      await expect(links).toHaveCount(count);

      for (let index = 0; index < count; index++) {
        const card = cards.nth(index);
        const title = (await card.getByRole("heading", { level: 3 }).textContent()).trim();
        await expect(links.nth(index)).toHaveAttribute("href", `#${await card.getAttribute("id")}`);
        await expect(links.nth(index)).toHaveAccessibleName(`${index + 1}. ${title}`);
      }

      // Fixo à esquerda, fora da coluna de leitura.
      const position = await rail.evaluate((el) => getComputedStyle(el).position);
      expect(position).toBe("fixed");
      const railBox = await rail.boundingBox();
      const cardBox = await cards.first().boundingBox();
      expect(railBox.x + railBox.width).toBeLessThanOrEqual(cardBox.x);

      const hash = await page.evaluate(() => window.location.hash);
      await links.nth(1).click();
      await expect(cards.nth(1)).toBeInViewport();
      await expect(cards.nth(1)).toBeFocused();
      await expect(links.nth(1)).toHaveAttribute("aria-current", "true");
      // O link não troca a rota.
      expect(await page.evaluate(() => window.location.hash)).toBe(hash);
    });

    test("só aparece na aba Resumo", async ({ page }) => {
      await open(page, RESULT);
      await page.getByRole("tab", { name: "Linha do tempo" }).click();
      await expect(page.getByRole("navigation", { name: "Erros por custo" })).toHaveCount(0);
    });
  });

  test.describe("360 px", () => {
    test.use({ viewport: { width: 360, height: 740 } });

    test("vira faixa no topo da lista, não é fixo e não rola de lado", async ({ page }) => {
      await open(page, RESULT, "light");
      const rail = page.getByRole("navigation", { name: "Erros por custo" });
      await expect(rail).toBeAttached();
      expect(await rail.evaluate((el) => getComputedStyle(el).position)).toBe("static");
      const box = await rail.boundingBox();
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(360);
      // Fica antes do primeiro cartão de erro.
      const before = await page.evaluate(() => {
        const nav = document.querySelector("nav[aria-label='Erros por custo']");
        const card = document.getElementById("erro-1");
        return Boolean(nav.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING);
      });
      expect(before).toBe(true);
      const sizes = await page.evaluate(() => ({
        scroll: document.documentElement.scrollWidth,
        client: document.documentElement.clientWidth,
      }));
      expect(sizes.scroll).toBeLessThanOrEqual(sizes.client);
    });
  });
});
