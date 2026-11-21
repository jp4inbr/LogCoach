// Ícones das magias no resultado, no navegador de verdade: carregam, ficam à esquerda do nome e
// na mesma linha, sem rolagem horizontal, nos dois temas e nos dois tamanhos de tela. Com
// PRINTS_DIR definido, também salva as capturas de tela (sem ela, não escreve nada em disco).
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import icons from "../src/data/spell-icons.json" with { type: "json" };
import { analysis, happyRoutes, mockApi, seedStorage, seriousViolations } from "./helpers.js";

const PRINTS_DIR = process.env.PRINTS_DIR;
if (PRINTS_DIR) mkdirSync(PRINTS_DIR, { recursive: true });
const shot = (target, name) =>
  PRINTS_DIR ? target.screenshot({ path: join(PRINTS_DIR, name) }) : null;

const SIZES = {
  desktop: { width: 1280, height: 900 },
  celular: { width: 390, height: 844 },
};
const THEMES = { claro: "light", escuro: "dark" };

// Cada .spell-ref visível: o ícone termina antes do início da primeira palavra e o centro vertical
// dele cai dentro da caixa dela (mesma linha). Todo span cujo ID está no catálogo tem de ter a
// imagem carregada (uma imagem que falha some no onError e não pode escapar da checagem).
async function checkIconsBesideText(page, scope, catalogIds) {
  return page.evaluate(
    ({ selector, catalogIds }) => {
      const problems = [];
      let checked = 0;
      for (const ref of document.querySelectorAll(`${selector} .spell-ref`)) {
        if (ref.closest("details:not([open])")) continue;
        const id = ref.getAttribute("data-spell-id");
        if (!catalogIds.includes(id)) {
          problems.push(`span sem ícone no catálogo: ${ref.textContent}`);
          continue;
        }
        const img = ref.querySelector("img");
        if (!img || !img.complete || !img.naturalWidth) {
          problems.push(`ícone ${id} ausente ou quebrado: ${ref.textContent}`);
          continue;
        }
        if (!ref.getClientRects().length) continue;
        const lead = ref.querySelector(".spell-lead");
        const textNode = [...lead.childNodes].find((n) => n.nodeType === 3 && n.textContent.trim());
        if (!textNode) continue;
        const range = document.createRange();
        range.selectNodeContents(textNode);
        const text = range.getBoundingClientRect();
        const box = img.getBoundingClientRect();
        if (!box.width || !text.width) continue;
        checked++;
        const centre = box.top + box.height / 2;
        if (box.right > text.left + 0.5)
          problems.push(`ícone não está à esquerda: ${ref.textContent}`);
        if (centre < text.top || centre > text.bottom)
          problems.push(`ícone fora da linha do texto: ${ref.textContent}`);
        if (lead.firstElementChild !== img)
          problems.push(`img não é o primeiro filho: ${ref.textContent}`);
      }
      return { checked, problems };
    },
    { selector: scope, catalogIds },
  );
}

// O conteúdo de cada rótulo (linha do tempo) e cabeçalho de linha (tabela por habilidade) não
// passa da borda direita da própria célula: nome longo quebra em vez de invadir a trilha.
const checkLabelsInside = (page) =>
  page.evaluate(() => {
    const problems = [];
    let checked = 0;
    const cells = document.querySelectorAll(".timeline-label, table.abilities th[scope='row']");
    for (const cell of cells) {
      if (!cell.getClientRects().length || !cell.textContent.trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(cell);
      checked++;
      const over = range.getBoundingClientRect().right - cell.getBoundingClientRect().right;
      if (over > 0.5) problems.push(`"${cell.textContent}" passa ${over.toFixed(1)} px da célula`);
    }
    return { checked, problems };
  });

const horizontalOverflow = (page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

const allImagesLoaded = (page) =>
  page.evaluate(async () => {
    // Ignora ícones dentro de <details> recolhidos (content-visibility: hidden não dispara lazy load).
    const imgs = [...document.querySelectorAll("img.spell-icon")].filter(
      (img) => !img.closest("details:not([open])") && img.getClientRects().length > 0,
    );
    // Imagem preguiçosa só carrega perto da tela: rola até cada uma e espera ela chegar.
    for (const img of imgs) {
      img.scrollIntoView({ block: "center" });
      if (!img.complete) await new Promise((ok) => ((img.onload = ok), (img.onerror = ok)));
    }
    window.scrollTo(0, 0);
    return {
      total: imgs.length,
      broken: imgs.filter((i) => !(i.complete && i.naturalWidth > 0)).length,
    };
  });

for (const [themeName, scheme] of Object.entries(THEMES)) {
  for (const [sizeName, viewport] of Object.entries(SIZES)) {
    test.describe(`${themeName}, ${sizeName}`, () => {
      test.use({ colorScheme: scheme, viewport });

      test("ícones carregam, ficam à esquerda do nome e a página não rola de lado", async ({
        page,
      }) => {
        const badIcons = [];
        page.on("response", (response) => {
          if (response.url().includes("/icons/") && response.status() >= 400)
            badIcons.push(`${response.status()} ${response.url()}`);
        });
        const catalogIds = Object.keys(icons);
        const result = analysis();
        await seedStorage(page, { "logcoach.theme": scheme });
        await mockApi(page, happyRoutes());
        await page.goto(`/#/analise/${result.id}`);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await page.locator(".mistake").first().waitFor();

        // Resumo (cards).
        expect(await page.locator("body").innerText()).not.toContain("{{");
        let loaded = await allImagesLoaded(page);
        expect(loaded.total).toBeGreaterThan(0);
        expect(loaded.broken).toBe(0);
        let layout = await checkIconsBesideText(page, "body", catalogIds);
        expect(layout.checked).toBeGreaterThan(0);
        expect(layout.problems).toEqual([]);
        expect(await seriousViolations(page)).toEqual([]);
        expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
        if (PRINTS_DIR) {
          await page.screenshot({
            path: join(PRINTS_DIR, `resultado-${themeName}-${sizeName}.png`),
            fullPage: true,
          });
          if (sizeName === "desktop" && themeName === "claro")
            await shot(page.locator(".mistake").first(), "card-erro-claro.png");
        }

        // Linha do tempo.
        await page.getByRole("tab", { name: "Linha do tempo" }).click();
        await page.locator(".timeline-label img.spell-icon").first().waitFor();
        loaded = await allImagesLoaded(page);
        expect(loaded.broken).toBe(0);
        layout = await checkIconsBesideText(page, ".timeline", catalogIds);
        expect(layout.checked).toBeGreaterThan(0);
        expect(layout.problems).toEqual([]);
        let labels = await checkLabelsInside(page);
        expect(labels.checked).toBeGreaterThan(0);
        expect(labels.problems).toEqual([]);
        expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
        if (sizeName === "desktop" && themeName === "claro")
          await shot(page.locator(".timeline"), "linha-do-tempo-claro-desktop.png");

        // Regras e tabela por habilidade.
        await page.getByRole("tab", { name: "Todas as regras" }).click();
        await page.locator("table.rules").waitFor();
        await page.locator("table.rules details > summary").first().click();
        expect(await page.locator("body").innerText()).not.toContain("{{");
        loaded = await allImagesLoaded(page);
        expect(loaded.broken).toBe(0);
        layout = await checkIconsBesideText(page, "body", catalogIds);
        expect(layout.checked).toBeGreaterThan(0);
        expect(layout.problems).toEqual([]);
        expect(await page.locator("table.abilities th img.spell-icon").count()).toBeGreaterThan(0);
        labels = await checkLabelsInside(page);
        expect(labels.checked).toBeGreaterThan(0);
        expect(labels.problems).toEqual([]);
        expect(await seriousViolations(page)).toEqual([]);
        if (sizeName === "desktop" && themeName === "escuro")
          await shot(page.locator("table.rules"), "regras-escuro.png");

        expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
        expect(badIcons).toEqual([]);
      });
    });
  }
}
