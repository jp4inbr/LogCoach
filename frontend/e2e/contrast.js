// Contraste real do texto sobre o cenário (as cidades pintadas atrás das telas). O axe não
// mede texto sobre imagem; aqui o próprio navegador desenha a tela sem o texto e cada texto
// visível é comparado com os pixels que ficam atrás dele.

/** Espera a cidade do tema ativo carregar e as transições do cenário terminarem. */
export async function waitForBackdrop(page) {
  await page.waitForFunction(() =>
    [...document.querySelectorAll(".backdrop-city")].some(
      (pic) =>
        getComputedStyle(pic).display !== "none" &&
        getComputedStyle(pic).opacity === "1" &&
        pic.querySelector("img").complete &&
        pic.querySelector("img").naturalWidth > 0,
    ),
  );
  // Imagem decodificada, fonte carregada e transições terminadas (fade da cidade, desfoque das
  // telas de uso, cores do tema). Ficam de fora as animações sem fim (pulso de espera) e as
  // presas à rolagem (o véu do início), que não "terminam".
  await page.evaluate(async () => {
    await Promise.all(
      [...document.querySelectorAll(".backdrop-city img")].map((i) => i.decode().catch(() => {})),
    );
    await document.fonts.ready;
    const running = document
      .getAnimations()
      .filter(
        (a) =>
          a.timeline === document.timeline && a.effect?.getComputedTiming().iterations !== Infinity,
      );
    await Promise.all(running.map((a) => a.finished.catch(() => {})));
  });
  await page.waitForTimeout(100);
}

/**
 * Rola até `scrollY`, mede e devolve os textos abaixo do mínimo WCAG AA (4,5:1; 3:1 para
 * texto grande). Por texto, vale o 5º percentil do contraste entre a cor dele e os pixels da
 * caixa dele, o que ignora as bordas finas de um controle dentro da caixa.
 */
export async function measureTextContrast(page, scrollY = 0) {
  await page.evaluate((y) => window.scrollTo(0, y), scrollY);
  await waitForBackdrop(page);

  const items = await page.evaluate(() => {
    const out = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const seen = new Set();
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const el = node.parentElement;
      if (!el || seen.has(el) || !node.textContent.trim()) continue;
      // Fora da medida: enfeite, texto só para leitor de tela e controle desativado (o WCAG
      // não exige contraste dele); checkVisibility pula <details> fechado e opacidade 0.
      if (el.closest('[aria-hidden="true"], .sr-only, .skip, svg')) continue;
      if (el.closest(':disabled, [aria-disabled="true"]')) continue;
      seen.add(el);
      if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
      const style = getComputedStyle(el);
      const range = document.createRange();
      range.selectNodeContents(node);
      for (const r of range.getClientRects()) {
        if (r.width < 2 || r.height < 2) continue;
        if (r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth) continue;
        const size = parseFloat(style.fontSize);
        const bold = +style.fontWeight >= 700;
        out.push({
          text: node.textContent.trim().slice(0, 40),
          color: style.color,
          large: size >= 24 || (bold && size >= 18.66),
          rect: [r.left, r.top, r.width, r.height].map(Math.round),
        });
      }
    }
    return out;
  });

  // A tela sem texto: o que fica atrás de cada palavra.
  const hide = await page.addStyleTag({
    content:
      "*, *::placeholder { color: transparent !important; text-shadow: none !important; transition: none !important; " +
      "text-decoration-color: transparent !important; caret-color: transparent !important; }",
  });
  const shot = await page.screenshot();
  await hide.evaluate((el) => el.remove());

  return page.evaluate(
    async ({ items, b64 }) => {
      const img = new Image();
      img.src = `data:image/png;base64,${b64}`;
      await img.decode();
      const canvas = document.createElement("canvas");
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0);
      const dpr = img.width / innerWidth;
      const lum = (r, g, b) =>
        [r, g, b]
          .map((v) => v / 255)
          .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
          .reduce((acc, c, i) => acc + c * [0.2126, 0.7152, 0.0722][i], 0);
      const bad = [];
      for (const it of items) {
        const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(it.color);
        if (!m) continue;
        const fl = lum(+m[1], +m[2], +m[3]);
        const [x, y, w, h] = it.rect.map((v) => Math.round(v * dpr));
        const x0 = Math.max(0, x);
        const y0 = Math.max(0, y);
        const w0 = Math.min(img.width - x0, w);
        const h0 = Math.min(img.height - y0, h);
        if (w0 < 1 || h0 < 1) continue;
        const data = ctx.getImageData(x0, y0, w0, h0).data;
        const ratios = [];
        for (let i = 0; i < data.length; i += 4 * 3) {
          const bl = lum(data[i], data[i + 1], data[i + 2]);
          const [hi, lo] = fl > bl ? [fl, bl] : [bl, fl];
          ratios.push((hi + 0.05) / (lo + 0.05));
        }
        ratios.sort((a, b) => a - b);
        const ratio = ratios[Math.floor(ratios.length * 0.05)];
        const min = it.large ? 3 : 4.5;
        if (ratio < min) bad.push({ text: it.text, ratio: +ratio.toFixed(2), min });
      }
      return bad;
    },
    { items, b64: shot.toString("base64") },
  );
}
