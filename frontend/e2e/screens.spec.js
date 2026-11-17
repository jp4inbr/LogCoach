// Repaginação em todas as telas (fase 2): o mesmo idioma visual da tela inicial levado às
// telas internas, sem mudar comportamento. Aqui fica o que só o navegador mede: contraste
// real (axe), rolagem horizontal, cabeçalho em chips, faixa-título, foco visível, movimento
// reduzido, rede e as cores de significado (situação, jogador × top, aviso de exemplo).
import { expect, test } from "@playwright/test";
import { analysis, happyRoutes, mockApi, seedStorage, seriousViolations } from "./helpers.js";
import { h1, openScreen, SCREENS, SIZES, THEME_KEY, THEMES, tokenColor } from "./screens.js";

// ---------- W3: axe com contraste ----------

test.describe("W3: acessibilidade com contraste (axe) em todas as telas", () => {
  for (const theme of THEMES) {
    for (const name of Object.keys(SCREENS)) {
      test(`${name} (${theme})`, async ({ page }) => {
        await openScreen(page, name, theme);
        expect(await seriousViolations(page)).toEqual([]);
      });
    }
  }

  // As abas do resultado (linha do tempo e regras) também passam.
  for (const theme of THEMES) {
    for (const tab of ["Linha do tempo", "Todas as regras"]) {
      test(`resultado, aba ${tab} (${theme})`, async ({ page }) => {
        await openScreen(page, "resultado", theme);
        await page.getByRole("tab", { name: new RegExp(tab) }).click();
        expect(await seriousViolations(page)).toEqual([]);
      });
    }
  }
});

// ---------- W4: rolagem horizontal ----------

/** Página sem rolagem lateral; tabela que não cabe rola dentro de um contêiner próprio. */
async function checkOverflow(page, label) {
  const info = await page.evaluate(() => {
    const doc = document.documentElement;
    const tables = [...document.querySelectorAll("table")].map((table) => {
      let el = table.parentElement;
      let scroller = null;
      while (el && el !== document.body) {
        const ox = getComputedStyle(el).overflowX;
        if (ox === "auto" || ox === "scroll") {
          scroller = el;
          break;
        }
        el = el.parentElement;
      }
      const r = table.getBoundingClientRect();
      return {
        cls: table.className,
        inScroller: Boolean(scroller),
        fits: r.right <= doc.clientWidth + 0.5 && r.left >= -0.5,
      };
    });
    return { scroll: doc.scrollWidth, client: doc.clientWidth, tables };
  });
  expect(info.scroll, `${label}: rolagem lateral da página`).toBeLessThanOrEqual(info.client);
  for (const t of info.tables) {
    expect(t.inScroller || t.fits, `${label}: tabela .${t.cls} vaza sem rolar sozinha`).toBe(true);
  }
}

test.describe("W4: sem rolagem horizontal", () => {
  for (const size of SIZES) {
    test.describe(`${size.width}×${size.height}`, () => {
      test.use({ viewport: size });
      for (const theme of THEMES) {
        for (const name of Object.keys(SCREENS)) {
          test(`${name} (${theme})`, async ({ page }) => {
            await openScreen(page, name, theme);
            await checkOverflow(page, name);
            if (name === "resultado") {
              for (const tab of ["Linha do tempo", "Todas as regras"]) {
                await page.getByRole("tab", { name: new RegExp(tab) }).click();
                await checkOverflow(page, `${name}, aba ${tab}`);
              }
            }
          });
        }
      }
    });
  }
});

// ---------- W5: cabeçalho em chips ----------

test.describe("W5: cabeçalho em chips em todas as rotas", () => {
  for (const size of [SIZES[0], SIZES[2]]) {
    test.describe(`${size.width}px`, () => {
      test.use({ viewport: size });
      for (const name of Object.keys(SCREENS)) {
        test(name, async ({ page }) => {
          const screen = SCREENS[name];
          await openScreen(page, name, "dark");
          const nav = page.getByRole("navigation", { name: "Principal" });
          const links = screen.logged ? ["Analisar", "Planos", "Perfil"] : ["Analisar", "Planos"];
          for (const link of links) {
            const el = nav.getByRole("link", { name: link, exact: true });
            await expect(el).toBeVisible();
            if (link === screen.current) await expect(el).toHaveAttribute("aria-current", "page");
            else await expect(el).not.toHaveAttribute("aria-current");
            // Chip: borda fina, fundo próprio do token e cantos pouco arredondados.
            const style = await el.evaluate((node) => {
              const s = getComputedStyle(node);
              return {
                border: s.borderTopStyle,
                width: parseFloat(s.borderTopWidth),
                radius: parseFloat(s.borderTopLeftRadius),
                background: s.backgroundColor,
              };
            });
            expect(style.border, `${link}: borda do chip`).toBe("solid");
            expect(style.width).toBeGreaterThan(0);
            expect(style.radius).toBeLessThanOrEqual(6);
            expect(style.background).toBe(await tokenColor(page, "--hero-chip-bg"));
          }
          // Tema: botão-ícone; sem login, "● Entrar" com o ponto (enfeite fora do nome).
          await expect(nav.getByRole("button", { name: /Ativar tema/ })).toBeVisible();
          if (!screen.logged) {
            const entrar = nav.getByRole("link", { name: "Entrar", exact: true });
            await expect(entrar).toBeVisible();
            const dot = await entrar.evaluate((node) => {
              const s = getComputedStyle(node, "::before");
              return { content: s.content, background: s.backgroundColor, width: s.width };
            });
            expect(dot.content).toBe('""');
            expect(dot.width).toBe("7px");
            expect(dot.background).toBe(await tokenColor(page, "--hero-dot"));
          }

          const header = page.locator("header.topbar");
          const position = await header.evaluate((el) => getComputedStyle(el).position);
          if (screen.internal) {
            expect(position).not.toBe("absolute");
            const hb = await header.boundingBox();
            const mb = await page.locator("main").boundingBox();
            expect(mb.y).toBeGreaterThanOrEqual(hb.y + hb.height - 0.5);
          } else {
            expect(position).toBe("absolute");
          }
        });
      }
    });
  }
});

// ---------- W6: faixa-título ----------

test.describe("W6: faixa-título nas telas internas", () => {
  test.use({ viewport: SIZES[2] });
  for (const theme of THEMES) {
    for (const [name, screen] of Object.entries(SCREENS)) {
      if (!screen.internal) continue;
      test(`${name} (${theme})`, async ({ page }) => {
        await openScreen(page, name, theme);
        const bands = page.locator("main .page-band");
        if (screen.h1 === null) {
          // Estado de erro sem título: continua sem h1 (nada de texto novo) e sem faixa.
          await expect(h1(page)).toHaveCount(0);
          await expect(bands).toHaveCount(0);
          return;
        }
        await expect(bands).toHaveCount(1);
        const band = bands.first();
        const title = band.getByRole("heading", { level: 1 });
        await expect(title).toHaveCount(1);
        await expect(title).toHaveAccessibleName(screen.h1);
        // Só um h1 na tela, e ele é o da faixa.
        await expect(h1(page)).toHaveCount(1);
        // A faixa abre a tela: é o primeiro elemento do conteúdo.
        expect(
          await band.evaluate((el) => {
            const main = document.querySelector("main");
            const first = main.firstElementChild;
            return first === el || first.firstElementChild === el;
          }),
        ).toBe(true);
        // Fase 3: a faixa não pinta fundo próprio (o cenário da tela inicial aparece por trás,
        // em todas as telas); antes exigia o --hero-bg aqui. Sobretítulo em caixa alta.
        expect(await band.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(
          "rgba(0, 0, 0, 0)",
        );
        const eyebrow = band.locator(".eyebrow");
        await expect(eyebrow).toHaveCount(1);
        expect(await eyebrow.evaluate((el) => getComputedStyle(el).textTransform)).toBe(
          "uppercase",
        );
        // Mais baixa que a landing: não ocupa a primeira dobra.
        const box = await band.boundingBox();
        expect(box.height).toBeLessThan(SIZES[2].height / 2);
      });
    }
  }
});

// ---------- W7: teclado ----------

test.describe("W7: teclado e foco visível", () => {
  test.use({ viewport: SIZES[2] });
  for (const theme of THEMES) {
    for (const name of Object.keys(SCREENS)) {
      test(`${name} (${theme})`, async ({ page }) => {
        await openScreen(page, name, theme);
        // Recomeça do topo do documento: foco programático num marcador fora da ordem do Tab,
        // antes de tudo, para o próximo Tab partir do começo (e não do último clique).
        await page.evaluate(() => {
          const start = document.createElement("span");
          start.tabIndex = -1;
          document.body.prepend(start);
          start.focus();
        });
        const seen = [];
        for (let i = 0; i < 150; i++) {
          await page.keyboard.press("Tab");
          const info = await page.evaluate(() => {
            const el = document.activeElement;
            if (!el || el === document.body) return null;
            const s = getComputedStyle(el);
            return {
              key: `${el.tagName}#${el.id}.${el.className}|${el.textContent.trim().slice(0, 30)}`,
              name: el.getAttribute("aria-label") ?? el.textContent.trim().slice(0, 40),
              outline: s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0,
              shadow: s.boxShadow !== "none",
            };
          });
          if (!info || (seen.length && info.key === seen[0].key)) break;
          seen.push(info);
        }
        expect(seen.length).toBeGreaterThan(3);
        expect(seen[0].name).toBe("Pular para o conteúdo");
        for (const item of seen) {
          expect(item.outline || item.shadow, `foco visível em "${item.name}"`).toBe(true);
        }
      });
    }
  }
});

// ---------- W8: movimento reduzido ----------

test.describe("W8: movimento reduzido", () => {
  test.use({ viewport: SIZES[2] });
  for (const name of Object.keys(SCREENS)) {
    test(`${name}: nenhuma animação com reduce`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await openScreen(page, name, "dark");
      expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
    });
  }
});

// ---------- W9: rede ----------

test.describe("W9: nenhum pedido para fora de localhost e api.test", () => {
  test.use({ viewport: SIZES[2] });
  for (const name of Object.keys(SCREENS)) {
    test(name, async ({ page }) => {
      const hosts = [];
      page.on("request", (request) => {
        const url = new URL(request.url());
        if (url.protocol === "data:" || url.protocol === "blob:") return;
        hosts.push(url.hostname);
      });
      await openScreen(page, name, "dark");
      await page.mouse.wheel(0, 4000);
      await page.waitForLoadState("networkidle");
      expect(hosts.length).toBeGreaterThan(0);
      expect([...new Set(hosts)].filter((h) => h !== "localhost" && h !== "api.test")).toEqual([]);
    });
  }
});

// ---------- W11: cores de significado ----------

// Valores dos tokens antes da repaginação (docs/15): o significado não pode mudar.
const MEANING = {
  dark: {
    "--ok": "#4ade80",
    "--warn": "#fde047",
    "--warn-badge-fg": "#fde047",
    "--error": "#f87171",
    "--player": "#ff8906",
    "--top": "#22d3ee",
    "--luck": "#3b82f6",
  },
  light: {
    "--ok": "#166534",
    "--warn": "#dfa800",
    "--warn-badge-fg": "#9a5b00",
    "--error": "#b91c1c",
    "--player": "#dd6b00",
    "--top": "#0c7c9c",
    "--luck": "#2563eb",
  },
};
const TRANSLUCENT = {
  dark: {
    "--warn-bg": "rgba(253, 224, 71, 0.12)",
    "--warn-badge-bg": "rgba(253, 224, 71, 0.12)",
    "--error-bg": "rgba(248, 113, 113, 0.12)",
    "--ok-bg": "rgba(74, 222, 128, 0.12)",
  },
  light: {
    "--warn-bg": "rgba(180, 83, 9, 0.12)",
    "--warn-badge-bg": "rgb(255, 239, 168)",
    "--error-bg": "rgba(185, 28, 28, 0.09)",
    "--ok-bg": "rgba(22, 101, 52, 0.1)",
  },
};
const rgbOf = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
};

/** [seletor, propriedade, token] que precisam bater, por aba do resultado. */
const RESULT_CHECKS = {
  Resumo: [
    [".mistake:not(.mistake-erro)", "borderLeftColor", "--warn"],
    [".mistake-erro", "borderLeftColor", "--error"],
    [".gap-mistakes", "backgroundColor", "--error"],
    [".gap-luck", "backgroundColor", "--luck"],
    [".badge-atencao", "color", "--warn-badge-fg"],
    [".badge-atencao", "backgroundColor", "--warn-badge-bg"],
    [".badge-erro", "color", "--error"],
    [".badge-erro", "backgroundColor", "--error-bg"],
    [".notice-atencao", "backgroundColor", "--warn-bg"],
  ],
  "Linha do tempo": [
    [".mark-player", "backgroundColor", "--player"],
    [".mark-top", "backgroundColor", "--top"],
  ],
  "Todas as regras": [
    [".badge-ok", "color", "--ok"],
    [".badge-ok", "backgroundColor", "--ok-bg"],
    [".badge-atencao", "color", "--warn-badge-fg"],
    [".badge-erro", "color", "--error"],
  ],
};

async function expectMeaning(page, theme, checks, label) {
  for (const [selector, prop, token] of checks) {
    const target = page.locator(selector).first();
    expect(await page.locator(selector).count(), `${label}: ${selector} presente`).toBeGreaterThan(
      0,
    );
    const value = await target.evaluate((el, p) => getComputedStyle(el)[p], prop);
    const expected =
      MEANING[theme][token] !== undefined
        ? rgbOf(MEANING[theme][token])
        : TRANSLUCENT[theme][token];
    expect(expected, `${token} sem valor de referência`).toBeTruthy();
    expect(value, `${label}: ${selector} ${prop} = ${token}`).toBe(expected);
  }
}

test.describe("W11: cores de significado intactas", () => {
  test.use({ viewport: SIZES[2] });
  for (const theme of THEMES) {
    test(`resultado: situação, jogador × top, azar e aviso (${theme})`, async ({ page }) => {
      const result = analysis();
      result.result.source = "exemplo"; // mostra o aviso amarelo de exemplo
      await seedStorage(page, { [THEME_KEY]: theme });
      await mockApi(page, { ...happyRoutes(), [`GET /analyses/${result.id}`]: { body: result } });
      await page.goto(`/#/analise/${result.id}`);
      await expect(page.getByText("Resultado de exemplo")).toBeVisible();
      for (const [tab, checks] of Object.entries(RESULT_CHECKS)) {
        await page.getByRole("tab", { name: new RegExp(tab) }).click();
        await expectMeaning(page, theme, checks, `resultado/${tab}`);
      }
    });

    test(`escolher luta: aviso amarelo do relatório de exemplo (${theme})`, async ({ page }) => {
      await openScreen(page, "escolher luta com lista", theme);
      await expect(page.getByText("Relatório de exemplo")).toBeVisible();
      await expectMeaning(
        page,
        theme,
        [[".notice-atencao", "backgroundColor", "--warn-bg"]],
        "escolher luta",
      );
    });
  }
});
