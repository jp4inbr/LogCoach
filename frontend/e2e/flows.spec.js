// Fluxos principais no navegador, com a API do backend simulada (e2e/helpers.js). Os caminhos,
// corpos e códigos de erro seguem o item 12.3 da documentação técnica.
import { expect, test } from "@playwright/test";
import {
  analysis,
  apiError,
  happyRoutes,
  mockApi,
  REPORT_CODE,
  REPORT_LINK,
  report,
  seedStorage,
  session,
} from "./helpers.js";

const ME = {
  email: "voce@exemplo.com",
  created_at: "2026-10-01T12:00:00Z",
  plan: "gratis",
  analyses_this_month: 1,
  monthly_limit: 5,
};

async function pasteLink(page, link = REPORT_LINK) {
  await page.goto("/");
  await page.getByLabel("Link do relatório no Warcraft Logs").fill(link);
  await page.getByRole("button", { name: "Analisar" }).click();
}

test.describe("analisar uma luta", () => {
  test("do link ao resultado, com a pré-busca e o corpo certo da análise", async ({ page }) => {
    const api = await mockApi(page, happyRoutes());

    await pasteLink(page);
    await expect(page).toHaveURL(new RegExp(`#/relatorio/${REPORT_CODE}$`));

    // O servidor recebe o link normalizado (sem o #fight).
    await expect(page.getByRole("heading", { name: "The Venomous Abyss — Mítico" })).toBeVisible();
    expect(api.calls("POST /reports/resolve")[0].body).toEqual({
      url: `https://www.warcraftlogs.com/reports/${REPORT_CODE}`,
    });
    await expect(page.getByText("Relatório de exemplo")).toBeVisible();

    // Lutas indisponíveis: em cinza (aria-disabled) e com o motivo do servidor.
    const short = page.getByRole("button", { name: /luta 33/ });
    await expect(short).toHaveAttribute("aria-disabled", "true");
    await expect(short).toContainText("A luta tem menos de 60 s");
    const other = page.getByRole("button", { name: /Entombed Sentinels/ });
    await expect(other).toHaveAttribute("aria-disabled", "true");
    await expect(other).toContainText("Chefe ainda não suportado");

    // Clicar numa luta indisponível não faz nada: não busca Magos. O Playwright trata
    // aria-disabled como desabilitado e esperaria para sempre, por isso o force.
    await short.click({ force: true });
    await expect(page.getByRole("heading", { name: "2. Escolha seu Mago Arcano" })).toHaveCount(0);
    expect(api.calls(`GET /reports/${REPORT_CODE}/fights/33/players`)).toHaveLength(0);

    const fight = page.getByRole("button", { name: /Nek'zali.*luta 34/ });
    await expect(fight).not.toHaveAttribute("aria-disabled", "true");
    await fight.click();
    await expect(fight).toHaveAttribute("aria-pressed", "true");

    const harmonist = page.getByRole("radio", { name: /Harmonist/ });
    await expect(harmonist).toBeVisible();
    await expect(page.getByText("Mago Arcano · item level 327")).toBeVisible();

    // Clicar no personagem dispara a pré-busca depois de ~1 s.
    await harmonist.click();
    await expect
      .poll(() => api.calls(`POST /reports/${REPORT_CODE}/fights/34/prefetch`).length)
      .toBe(1);
    expect(api.calls(`POST /reports/${REPORT_CODE}/fights/34/prefetch`)[0].body).toEqual({
      actor_id: 455,
    });

    await page.getByRole("button", { name: "Analisar" }).click();
    await expect(page.getByRole("heading", { name: "Analisando sua luta" })).toBeVisible();
    await expect(page.getByText("Comparando com os melhores")).toBeVisible();
    expect(api.calls("POST /analyses")[0].body).toEqual({
      report_code: REPORT_CODE,
      fight_id: 34,
      actor_id: 455,
    });

    // Resultado: as etapas levam alguns segundos antes de abrir a tela.
    await expect(page).toHaveURL(/#\/analise\/7dbcd6251c8c4000818a61ea67785e36$/, {
      timeout: 15_000,
    });
    await expect(
      page.getByRole("heading", { level: 1, name: "Nek'zali, a Enrosca-almas" }),
    ).toBeVisible();
    await expect(page.getByText(/Harmonist · Mago Arcano · item level 327/)).toBeVisible();
    await expect(page.getByText("Os tops fizeram 18% mais dano")).toBeVisible();

    // Nomes dos tops ocultos por padrão (RF25).
    await page.locator(".compared > summary").click();
    await expect(
      page
        .getByRole("cell", { name: "Top 1", exact: true })
        .or(page.getByRole("rowheader", { name: "Top 1", exact: true })),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Mostrar nomes" })).toBeDisabled();
    await expect(page.getByText("Nomes reais indisponíveis nos dados de exemplo.")).toBeVisible();
    expect(api.unmatched).toEqual([]);
  });

  test("mostra o aviso de exemplo quando a comparação usa tops de exemplo", async ({ page }) => {
    const result = analysis();
    result.result.comparison.sample = true;
    await mockApi(page, { ...happyRoutes(), [`GET /analyses/${result.id}`]: { body: result } });
    await page.goto(`/#/analise/${result.id}`);
    await expect(page.getByText("Comparação com tops de exemplo")).toBeVisible();
  });

  test("RF25: com nomes reais, ficam ocultos até o botão e a escolha é lembrada", async ({
    page,
  }) => {
    const result = analysis();
    result.result.comparison.players.forEach((p, i) => {
      p.name = `Fulano${i + 1}`;
      p.server = "Servidor";
    });
    await mockApi(page, { ...happyRoutes(), [`GET /analyses/${result.id}`]: { body: result } });
    await page.goto(`/#/analise/${result.id}`);
    await page.locator(".compared > summary").click();

    await expect(page.getByRole("rowheader", { name: "Fulano1 (Servidor)" })).toHaveCount(0);
    const eye = page.getByRole("button", { name: "Mostrar nomes" });
    await expect(eye).toHaveAttribute("aria-pressed", "false");
    await eye.click();
    await expect(page.getByRole("rowheader", { name: "Fulano1 (Servidor)" })).toBeVisible();
    await expect(eye).toHaveAttribute("aria-pressed", "true");

    await page.reload();
    await page.locator(".compared > summary").click();
    await expect(page.getByRole("rowheader", { name: "Fulano1 (Servidor)" })).toBeVisible();
  });

  test("análise de uma luta que não é Kill ou com a lista ao vivo: luta subindo fica bloqueada", async ({
    page,
  }) => {
    const live = report();
    live.fights[1] = {
      ...live.fights[1],
      in_progress: true,
      supported: false,
      unsupported_reason: "A luta ainda está subindo para o Warcraft Logs.",
    };
    await mockApi(page, { ...happyRoutes(), "POST /reports/resolve": { body: live } });
    await pasteLink(page);
    const uploading = page.getByRole("button", { name: /Nek'zali.*luta 34/ });
    await expect(uploading).toHaveAttribute("aria-disabled", "true");
    await expect(page.getByText("Subindo…")).toBeVisible();
  });
});

test.describe("erros ao abrir o relatório", () => {
  test("link inválido: mensagem no campo e nenhuma chamada à API", async ({ page }) => {
    const api = await mockApi(page, happyRoutes());
    await pasteLink(page, "https://google.com");
    await expect(
      page.getByText(
        "Esse link não parece ser do Warcraft Logs. Ele deve começar com warcraftlogs.com/reports/",
      ),
    ).toBeVisible();
    await expect(page.getByLabel("Link do relatório no Warcraft Logs")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    await expect(page).toHaveURL(/#?\/?$/);
    expect(api.all()).toHaveLength(0);

    // Escrever de novo limpa o erro.
    await page.getByLabel("Link do relatório no Warcraft Logs").fill("x");
    await expect(page.locator("#link-error")).toHaveCount(0);
  });

  test("campo vazio pede o link", async ({ page }) => {
    await mockApi(page, happyRoutes());
    await page.goto("/");
    await page.getByRole("button", { name: "Analisar" }).click();
    await expect(page.getByText("Cole o link do seu log do Warcraft Logs.")).toBeVisible();
  });

  test("o botão de exemplo preenche o link do kill de referência", async ({ page }) => {
    await mockApi(page, happyRoutes());
    await page.goto("/");
    await page.getByRole("button", { name: "Usar o log de exemplo" }).click();
    await expect(page.getByLabel("Link do relatório no Warcraft Logs")).toHaveValue(REPORT_LINK);
  });

  test("Warcraft Logs fora do ar: mensagem do servidor e Tentar de novo", async ({ page }) => {
    const message = "O Warcraft Logs está fora do ar no momento. Tente de novo em alguns minutos.";
    const api = await mockApi(page, {
      ...happyRoutes(),
      "POST /reports/resolve": [apiError(503, "wcl_unavailable", message), { body: report() }],
    });
    await pasteLink(page);
    await expect(page.getByText("Não deu para abrir esse relatório")).toBeVisible();
    await expect(page.getByText(message)).toBeVisible();

    await page.getByRole("button", { name: "Tentar de novo" }).click();
    await expect(page.getByRole("heading", { name: "The Venomous Abyss — Mítico" })).toBeVisible();
    expect(api.calls("POST /reports/resolve")).toHaveLength(2);
  });

  test("relatório privado: só oferece trocar o link", async ({ page }) => {
    await mockApi(page, {
      ...happyRoutes(),
      "POST /reports/resolve": apiError(
        404,
        "report_not_available",
        "Esse relatório é privado ou não existe.",
      ),
    });
    await pasteLink(page);
    await expect(page.getByText("Esse relatório é privado ou não existe.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Tentar de novo" })).toHaveCount(0);
    await page.getByRole("link", { name: "← Trocar o link" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Descubra os erros");
  });

  test("falha ao buscar os Magos da luta: Tentar de novo", async ({ page }) => {
    const key = `GET /reports/${REPORT_CODE}/fights/34/players`;
    await mockApi(page, {
      ...happyRoutes(),
      [key]: [
        apiError(503, "wcl_unavailable", "Warcraft Logs fora do ar."),
        { body: { report_code: REPORT_CODE, fight_id: 34, players: [] } },
      ],
    });
    await pasteLink(page);
    await page.getByRole("button", { name: /Nek'zali.*luta 34/ }).click();
    await expect(page.getByText("Não deu para buscar os personagens da luta")).toBeVisible();
    await page.getByRole("button", { name: "Tentar de novo" }).click();
    await expect(page.getByText("Não achamos nenhum Mago Arcano nessa luta")).toBeVisible();
  });

  test("análise com Warcraft Logs fora do ar mostra o erro e deixa tentar de novo", async ({
    page,
  }) => {
    const message = "O Warcraft Logs não respondeu a tempo. Tente de novo.";
    const result = analysis();
    const api = await mockApi(page, {
      ...happyRoutes(),
      "POST /analyses": [apiError(503, "wcl_unavailable", message), { body: result }],
    });
    await pasteLink(page);
    await page.getByRole("button", { name: /Nek'zali.*luta 34/ }).click();
    await page.getByRole("button", { name: "Analisar" }).click();
    await expect(page.getByText("A análise não foi concluída")).toBeVisible();
    await expect(page.getByText(message)).toBeVisible();
    await page.getByRole("button", { name: "Tentar de novo" }).click();
    await expect(page).toHaveURL(/#\/analise\//, { timeout: 15_000 });
    expect(api.calls("POST /analyses")).toHaveLength(2);
  });
});

test.describe("conta", () => {
  test("login: guarda o token, troca o cabeçalho e abre o perfil", async ({ page }) => {
    const api = await mockApi(page, {
      "POST /auth/login": { body: { access_token: "token-do-login", token_type: "bearer" } },
      "GET /me": { body: ME },
      "GET /me/analyses": { body: [] },
    });
    await page.goto("/#/entrar?modo=login");
    await expect(page.getByRole("link", { name: "Entrar" }).first()).toBeVisible();

    await page.getByLabel("E-mail").fill("  Voce@Exemplo.com ");
    await page.getByLabel("Senha").fill("senha-segura-1");
    await page.getByRole("button", { name: "Entrar" }).last().click();

    await expect(page).toHaveURL(/#\/perfil$/);
    await expect(page.getByRole("heading", { name: "Seu perfil" })).toBeVisible();
    expect(api.calls("POST /auth/login")[0].body).toEqual({
      email: "Voce@Exemplo.com",
      password: "senha-segura-1",
    });
    expect(api.calls("GET /me/analyses")[0].authorization).toBe("Bearer token-do-login");

    const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("logcoach.session")));
    expect(stored).toEqual({ token: "token-do-login", email: "voce@exemplo.com" });

    const nav = page.getByRole("navigation", { name: "Principal" });
    await expect(nav.getByRole("link", { name: "Perfil" })).toBeVisible();
    await expect(nav.getByRole("button", { name: "Sair" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Entrar" })).toHaveCount(0);

    // Sair limpa a sessão e volta o botão Entrar.
    await nav.getByRole("button", { name: "Sair" }).click();
    await expect(nav.getByRole("link", { name: "Entrar" })).toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem("logcoach.session"))).toBeNull();
  });

  test("login com senha errada mostra a mensagem do servidor e não guarda sessão", async ({
    page,
  }) => {
    await mockApi(page, {
      "POST /auth/login": apiError(401, "invalid_credentials", "E-mail ou senha incorretos."),
    });
    await page.goto("/#/entrar?modo=login");
    await page.getByLabel("E-mail").fill("voce@exemplo.com");
    await page.getByLabel("Senha").fill("errada");
    await page.getByRole("button", { name: "Entrar" }).last().click();
    await expect(page.getByRole("alert")).toHaveText("E-mail ou senha incorretos.");
    expect(await page.evaluate(() => localStorage.getItem("logcoach.session"))).toBeNull();
  });

  test("validação no campo antes de enviar", async ({ page }) => {
    const api = await mockApi(page, {});
    await page.goto("/#/entrar?modo=cadastro");
    await page.getByLabel("E-mail").fill("sem-arroba");
    await page.getByLabel("Senha").fill("curta");
    await page.getByRole("button", { name: "Criar conta" }).last().click();
    await expect(page.getByText("Digite um e-mail válido, como voce@exemplo.com.")).toBeVisible();
    await expect(page.getByText("A senha precisa ter pelo menos 8 caracteres.")).toBeVisible();
    expect(api.all()).toHaveLength(0);
  });

  test("cadastro: cria a conta, guarda o token e volta para a página de origem", async ({
    page,
  }) => {
    const api = await mockApi(page, {
      ...happyRoutes(),
      "POST /auth/register": {
        status: 201,
        body: { access_token: "token-cadastro", token_type: "bearer" },
      },
      "GET /me": { body: ME },
    });
    await page.goto(
      `/#/entrar?modo=cadastro&depois=${encodeURIComponent(`/relatorio/${REPORT_CODE}`)}`,
    );
    await expect(page.getByRole("heading", { name: "Crie sua conta grátis" })).toBeVisible();
    await page.getByLabel("E-mail").fill("novo@exemplo.com");
    await page.getByLabel("Senha").fill("senha-segura-1");
    await page.getByRole("button", { name: "Criar conta" }).last().click();

    await expect(page).toHaveURL(new RegExp(`#/relatorio/${REPORT_CODE}$`));
    expect(api.calls("POST /auth/register")[0].body).toEqual({
      email: "novo@exemplo.com",
      password: "senha-segura-1",
    });
    const nav = page.getByRole("navigation", { name: "Principal" });
    await expect(nav.getByRole("link", { name: "Perfil" })).toBeVisible();
    await expect(nav.getByRole("button", { name: "Sair" })).toBeVisible();
  });

  test("e-mail já cadastrado mostra o erro do servidor", async ({ page }) => {
    await mockApi(page, {
      "POST /auth/register": apiError(
        409,
        "email_taken",
        "Esse e-mail já tem conta. Tente entrar.",
      ),
    });
    await page.goto("/#/entrar?modo=cadastro");
    await page.getByLabel("E-mail").fill("novo@exemplo.com");
    await page.getByLabel("Senha").fill("senha-segura-1");
    await page.getByRole("button", { name: "Criar conta" }).last().click();
    await expect(page.getByRole("alert")).toHaveText("Esse e-mail já tem conta. Tente entrar.");
  });

  test("sessão vencida guardada: sai da conta sozinha", async ({ page }) => {
    await seedStorage(page, session("token-velho"));
    await mockApi(page, {
      "GET /me": apiError(401, "invalid_token", "Sua sessão expirou. Entre de novo."),
    });
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: "Principal" });
    await expect(nav.getByRole("link", { name: "Entrar" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Perfil" })).toHaveCount(0);
  });
});

test.describe("limite do plano", () => {
  const message = "Você já usou as 5 análises grátis deste mês. Volte mês que vem.";

  test("conta sem análises no mês: mostra a mensagem e leva aos planos", async ({ page }) => {
    await seedStorage(page, session());
    await mockApi(page, {
      ...happyRoutes(),
      "GET /me": { body: ME },
      "POST /analyses": apiError(403, "plan_limit", message),
    });
    await pasteLink(page);
    await page.getByRole("button", { name: /Nek'zali.*luta 34/ }).click();
    await page.getByRole("button", { name: "Analisar" }).click();

    await expect(page.getByText("A análise não foi concluída")).toBeVisible();
    await expect(page.getByText(message)).toBeVisible();
    await page.getByRole("link", { name: "Ver planos" }).click();
    await expect(page.getByRole("heading", { name: "Escolha como quer evoluir" })).toBeVisible();
    await expect(page.getByText("Seu plano atual")).toBeVisible();
  });

  test("sem conta: a análise de demonstração (não guardada) bloqueia a próxima", async ({
    page,
  }) => {
    const api = await mockApi(page, happyRoutes());
    await pasteLink(page);
    await page.getByRole("button", { name: /Nek'zali.*luta 34/ }).click();
    await page.getByRole("button", { name: "Analisar" }).click();
    await expect(page).toHaveURL(/#\/analise\//, { timeout: 15_000 });
    expect(api.calls("POST /analyses")[0].authorization).toBeNull();

    // Volta para escolher outra luta: a demonstração já foi usada.
    await page.getByRole("link", { name: "← Escolher outra luta" }).click();
    await expect(page.getByText("Você já usou a análise de demonstração")).toBeVisible();
    await expect(page.getByRole("button", { name: "Analisar" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Criar conta grátis" })).toHaveAttribute(
      "href",
      new RegExp(`modo=cadastro&depois=.*${REPORT_CODE}`),
    );
  });
});
