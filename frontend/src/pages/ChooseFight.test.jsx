import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AuthProvider from "../components/AuthProvider.jsx";
import { axeViolations } from "../test/axe.js";
import analysisFixture from "../test/fixtures/analysis.json";
import playersFixture from "../test/fixtures/players.json";
import reportFixture from "../test/fixtures/report.json";
import { apiError, lerSessao, mockApi, setSession } from "../test/mockApi.js";
import ChooseFight from "./ChooseFight.jsx";

const CODE = "XhrmBaYkGCAQjH2D";
const MIN = 60_000;

// --- dados de apoio, derivados das respostas reais (modo exemplo) ----------------------

// Uma luta que o Warcraft Logs ainda está recebendo (log ao vivo).
const MOTIVO_SUBINDO =
  "A luta ainda está subindo para o Warcraft Logs. Ela fica disponível aqui assim que terminar.";
function subindo(id) {
  return {
    ...reportFixture.fights[0],
    id,
    duration_s: 0,
    in_progress: true,
    unsupported_code: "in_progress",
    unsupported_reason: MOTIVO_SUBINDO,
  };
}

function pausada(id) {
  return {
    ...reportFixture.fights[0],
    id,
    duration_s: 90,
    upload_paused: true,
    unsupported_code: "upload_paused",
    unsupported_reason: "O upload dessa luta parou no meio. Envie o log de novo.",
  };
}

// Outra luta que pode ser analisada (cópia do kill de referência com outro id).
function suportada(id, duracao = 301) {
  return { ...reportFixture.fights[1], id, kill: false, duration_s: duracao };
}

// Lista de lutas da resposta de /reports/resolve. `n` desloca o fetched_at (cada busca nova do
// servidor traz uma hora nova; a mesma hora = o servidor devolveu o que já tinha).
function lista({ n = 0, fights, ...resto } = {}) {
  const base = structuredClone(reportFixture);
  return {
    ...base,
    sample: false,
    fetched_at: new Date(Date.parse(base.fetched_at) + n * 1000).toISOString(),
    fights: fights ?? base.fights,
    ...resto,
  };
}
const comLutas = (...extras) => [...reportFixture.fights, ...extras];

function guardada(extra = {}) {
  return lista({
    stale: true,
    stale_code: "wcl_unavailable",
    stale_message: "O Warcraft Logs está fora do ar.",
    ...extra,
  });
}

const hora = (iso) =>
  new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

const DOIS_MAGOS = {
  ...playersFixture,
  players: [
    { actor_id: 455, name: "Harmonist", server: "Reino Um", spec: "Mago Arcano", item_level: 327 },
    {
      actor_id: 460,
      name: "Harmonist",
      server: "Reino Dois",
      spec: "Mago Arcano",
      item_level: 325,
    },
    {
      actor_id: 470,
      name: "Outra Maga",
      server: "Reino Um",
      spec: "Mago Arcano",
      item_level: null,
    },
  ],
};

const ROTA_JOGADORES = `GET /reports/${CODE}/fights/34/players`;
const ROTA_PREFETCH = `POST /reports/${CODE}/fights/34/prefetch`;

function analiseSalva(saved = true) {
  return { body: { ...analysisFixture, saved } };
}

// --- renderização -------------------------------------------------------------------

function abrir(rotas = {}, { logado = false } = {}) {
  if (logado) setSession();
  const api = mockApi({
    "POST /reports/resolve": { body: lista() },
    [ROTA_JOGADORES]: { body: playersFixture },
    [ROTA_PREFETCH]: { status: 202, body: { status: "started" } },
    "POST /analyses": analiseSalva(),
    "GET /me": { body: {} },
    ...rotas,
  });
  const view = render(
    <AuthProvider>
      <ChooseFight code={CODE} />
    </AuthProvider>,
  );
  return { api, ...view };
}

let user;
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
});
afterEach(() => {
  vi.useRealTimers();
  delete document.visibilityState;
});

const aguardarLista = () => screen.findByRole("heading", { level: 1 });
const luta = (id) => screen.getByRole("button", { name: new RegExp(`luta ${id}(?!\\d)`) });
// Avança o relógio em passos, cada um dentro do seu act: os efeitos do React (que armam o
// próximo timer) só rodam quando o act fecha, então um único salto grande pularia etapas.
async function avancar(ms) {
  const passo = ms > 10_000 ? 5000 : 250;
  for (let feito = 0; feito < ms; feito += passo) {
    await act(() => vi.advanceTimersByTimeAsync(Math.min(passo, ms - feito)));
  }
}
// O botão principal é o último com esse nome (o "Tentar de novo" dos avisos vem antes).
const analisar = () =>
  screen.getAllByRole("button", { name: /^(Analisar|Tentar de novo)$/ }).at(-1);
const atualizar = () => screen.getByRole("button", { name: /^(Atualizar lutas|Atualizando…)$/ });
const chamadasResolve = (api) => api.calls("POST /reports/resolve").length;

async function abrirLuta34() {
  await user.click(luta(34));
  return screen.findByRole("radiogroup");
}

function esconderAba() {
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
}
function mostrarAba() {
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
  document.dispatchEvent(new Event("visibilitychange"));
}

// =========================================================================================

describe("ChooseFight: abrir o relatório", () => {
  it("mostra o carregamento e depois o título e o código do relatório", async () => {
    let liberar;
    const { api } = abrir({
      "POST /reports/resolve": () =>
        new Promise((resolve) => {
          liberar = () => resolve({ body: lista() });
        }),
    });

    expect(screen.getByText("Abrindo o relatório…")).toBeInTheDocument();
    await waitFor(() => expect(liberar).toBeTypeOf("function"));
    liberar();

    expect(
      await screen.findByRole("heading", { level: 1, name: "The Venomous Abyss — Mítico" }),
    ).toBeInTheDocument();
    expect(screen.getByText(`Relatório ${CODE}`)).toBeInTheDocument();
    expect(api.calls("POST /reports/resolve")[0].body).toEqual({
      url: `https://www.warcraftlogs.com/reports/${CODE}`,
    });
    expect(screen.getByRole("link", { name: "← Trocar o link" })).toHaveAttribute("href", "#/");
  });

  it("lista as lutas com chefe, dificuldade, duração e kill ou wipe", async () => {
    abrir();
    await aguardarLista();

    expect(screen.getAllByRole("button", { name: /luta \d+/ })).toHaveLength(4);
    expect(luta(34)).toHaveTextContent("Nek'zali, a Enrosca-almas");
    expect(luta(34)).toHaveTextContent("Mítico · luta 34 · 6:56");
    expect(luta(34)).toHaveTextContent("Kill");
    expect(luta(33)).toHaveTextContent("Mítico · luta 33 · 0:41");
    expect(luta(33)).toHaveTextContent("Wipe");
    expect(luta(47)).toHaveTextContent("The Lost Explorers");
    expect(luta(47)).toHaveTextContent("Mítico · luta 47 · 5:12");
    expect(screen.getByText(`Lista de ${hora(lista().fetched_at)}`)).toBeInTheDocument();
  });

  it("lutas que não podem ser analisadas ficam marcadas com o motivo, e o clique não faz nada", async () => {
    const { api } = abrir();
    await aguardarLista();

    for (const [id, motivo] of [
      [33, "A luta tem menos de 60 s. Escolha uma tentativa mais longa"],
      [41, "Chefe ainda não suportado"],
      [47, "Chefe ainda não suportado"],
    ]) {
      expect(luta(id)).toHaveAttribute("aria-disabled", "true");
      expect(luta(id)).toHaveAccessibleDescription(motivo);
      await user.click(luta(id));
    }

    // Nada foi escolhido: não busca Magos, não aparece a etapa 2.
    expect(api.calls(ROTA_JOGADORES)).toEqual([]);
    expect(luta(33)).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("heading", { name: "2. Escolha seu Mago Arcano" })).toBeNull();
    // A luta suportada não está desabilitada.
    expect(luta(34)).not.toHaveAttribute("aria-disabled");
  });

  it("sem luta escolhida, Analisar fica desabilitado e a dica diz o que fazer", async () => {
    abrir();
    await aguardarLista();

    expect(analisar()).toBeDisabled();
    expect(screen.getByText("Escolha uma luta para continuar.")).toBeInTheDocument();
  });

  it("relatório de exemplo (sem Warcraft Logs) tem o aviso amarelo; o real não", async () => {
    const { unmount } = abrir({ "POST /reports/resolve": { body: lista({ sample: true }) } });
    await aguardarLista();
    const aviso = screen.getByText("Relatório de exemplo").closest(".notice");
    expect(aviso).toHaveClass("notice-atencao");
    expect(aviso).toHaveTextContent("a lista de lutas vem de um arquivo de exemplo");
    unmount();

    abrir();
    await aguardarLista();
    expect(screen.queryByText("Relatório de exemplo")).not.toBeInTheDocument();
  });

  describe("erros", () => {
    it.each([
      [
        "link ou relatório privado",
        "report_not_available",
        404,
        "Relatório privado ou inexistente.",
      ],
      ["link inválido", "invalid_link", 422, "Esse link não parece ser do Warcraft Logs."],
      [
        "limite de consultas",
        "query_limit",
        503,
        "Limite do Warcraft Logs atingido. Tente em 5 min.",
      ],
    ])(
      "%s: mostra a mensagem e só oferece trocar o link",
      async (_nome, codigo, status, mensagem) => {
        const { api } = abrir({ "POST /reports/resolve": apiError(status, codigo, mensagem) });

        const aviso = await screen.findByRole("alert");
        expect(aviso).toHaveTextContent("Não deu para abrir esse relatório");
        expect(aviso).toHaveTextContent(mensagem);
        expect(screen.queryByRole("button", { name: "Tentar de novo" })).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: "← Trocar o link" })).toHaveAttribute("href", "#/");
        expect(chamadasResolve(api)).toBe(1);
      },
    );

    it("Warcraft Logs fora do ar: 'Tentar de novo' pede a lista outra vez e abre o relatório", async () => {
      const { api } = abrir({
        "POST /reports/resolve": [
          apiError(503, "wcl_unavailable", "O Warcraft Logs está fora do ar. Tente em instantes."),
          { body: lista() },
        ],
      });

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "O Warcraft Logs está fora do ar.",
      );
      await user.click(screen.getByRole("button", { name: "Tentar de novo" }));

      expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
        "The Venomous Abyss — Mítico",
      );
      expect(chamadasResolve(api)).toBe(2);
    });

    it("erro nosso (500) e rede fora também oferecem 'Tentar de novo'", async () => {
      const { unmount } = abrir({
        "POST /reports/resolve": {
          status: 500,
          body: "<html>Internal Server Error</html>",
          html: true,
        },
      });
      expect(await screen.findByRole("alert")).toHaveTextContent("Erro inesperado no LogCoach.");
      expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
      unmount();

      abrir({ "POST /reports/resolve": new TypeError("Failed to fetch") });
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "O servidor do LogCoach não respondeu.",
      );
      expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
    });

    it("sem violações de acessibilidade na tela de erro", async () => {
      const { container } = abrir({
        "POST /reports/resolve": apiError(
          503,
          "wcl_unavailable",
          "O Warcraft Logs está fora do ar.",
        ),
      });
      await screen.findByRole("alert");
      expect(await axeViolations(container)).toEqual([]);
    });
  });
});

describe("ChooseFight: escolher a luta e o Mago Arcano", () => {
  it("escolher a luta busca os Magos dela e marca o único como escolhido", async () => {
    const { api } = abrir({
      [ROTA_JOGADORES]: { delay: 500, body: playersFixture },
    });
    await aguardarLista();

    await user.click(luta(34));

    expect(luta(34)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Buscando os Magos Arcanos da luta…")).toBeInTheDocument();
    const grupo = await screen.findByRole("radiogroup", { name: "2. Escolha seu Mago Arcano" });
    expect(api.calls(ROTA_JOGADORES)).toHaveLength(1);
    // Os Magos são públicos: a rota é chamada sem token.
    expect(api.calls(ROTA_JOGADORES)[0].authorization).toBeNull();
    const harmonist = within(grupo).getByRole("radio", { name: /Harmonist/ });
    expect(harmonist).toBeChecked();
    expect(grupo).toHaveTextContent("Mago Arcano · item level 327");
    expect(analisar()).toBeEnabled();
    expect(screen.queryByText("Escolha uma luta para continuar.")).not.toBeInTheDocument();
  });

  it("vários Magos: nada vem marcado e o item level ausente não aparece", async () => {
    abrir({ [ROTA_JOGADORES]: { body: DOIS_MAGOS } });
    await aguardarLista();
    const grupo = await abrirLuta34();

    expect(within(grupo).getAllByRole("radio")).toHaveLength(3);
    for (const radio of within(grupo).getAllByRole("radio")) expect(radio).not.toBeChecked();
    expect(analisar()).toBeDisabled();
    expect(within(grupo).getByText("Reino Dois")).toBeInTheDocument();
    expect(grupo).toHaveTextContent("Mago Arcano · item level 325");
    const outra = within(grupo)
      .getByRole("radio", { name: /Outra Maga/ })
      .closest("label");
    expect(outra).not.toHaveTextContent("item level");

    await user.click(within(grupo).getByRole("radio", { name: /Reino Dois/ }));

    expect(within(grupo).getByRole("radio", { name: /Reino Dois/ })).toBeChecked();
    expect(analisar()).toBeEnabled();
  });

  it("personagem lembrado da última análise já vem marcado (nome + reino)", async () => {
    window.localStorage.setItem(
      "logcoach.character",
      JSON.stringify({ name: "Harmonist", server: "Reino Dois" }),
    );
    abrir({ [ROTA_JOGADORES]: { body: DOIS_MAGOS } });
    await aguardarLista();
    const grupo = await abrirLuta34();

    expect(within(grupo).getByRole("radio", { name: /Reino Dois/ })).toBeChecked();
    expect(within(grupo).getByRole("radio", { name: /Harmonist\s*Reino Um/ })).not.toBeChecked();
  });

  it("formato antigo (só o nome) com homônimos de reinos diferentes: não marca nenhum", async () => {
    window.localStorage.setItem("logcoach.character", JSON.stringify("Harmonist"));
    abrir({ [ROTA_JOGADORES]: { body: DOIS_MAGOS } });
    await aguardarLista();
    const grupo = await abrirLuta34();

    for (const radio of within(grupo).getAllByRole("radio")) expect(radio).not.toBeChecked();
    expect(analisar()).toBeDisabled();
  });

  it("voltar a uma luta já aberta não busca os Magos de novo; trocar de luta busca os da nova", async () => {
    const { api } = abrir({
      "POST /reports/resolve": { body: lista({ fights: comLutas(suportada(50)) }) },
      [`GET /reports/${CODE}/fights/50/players`]: { body: { ...playersFixture, fight_id: 50 } },
    });
    await aguardarLista();

    await abrirLuta34();
    await user.click(luta(50));
    await screen.findByRole("radio", { name: /Harmonist/ });
    await user.click(luta(34));

    expect(api.calls(ROTA_JOGADORES)).toHaveLength(1);
    expect(api.calls(`GET /reports/${CODE}/fights/50/players`)).toHaveLength(1);
    expect(luta(34)).toHaveAttribute("aria-pressed", "true");
    expect(luta(50)).toHaveAttribute("aria-pressed", "false");
  });

  it("erro ao buscar os Magos: mostra a mensagem e 'Tentar de novo' busca outra vez", async () => {
    const { api } = abrir({
      [ROTA_JOGADORES]: [
        apiError(503, "wcl_unavailable", "O Warcraft Logs não respondeu. Tente em instantes."),
        { body: playersFixture },
      ],
    });
    await aguardarLista();
    await user.click(luta(34));

    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent("Não deu para buscar os personagens da luta");
    expect(aviso).toHaveTextContent("O Warcraft Logs não respondeu. Tente em instantes.");
    expect(analisar()).toBeDisabled();

    await user.click(within(aviso).getByRole("button", { name: "Tentar de novo" }));

    expect(await screen.findByRole("radio", { name: /Harmonist/ })).toBeChecked();
    expect(api.calls(ROTA_JOGADORES)).toHaveLength(2);
  });

  it("luta sem nenhum Mago Arcano: avisa, e clicar na luta ou no botão busca de novo", async () => {
    const { api } = abrir({
      [ROTA_JOGADORES]: [
        { body: { ...playersFixture, players: [] } },
        { body: { ...playersFixture, players: [] } },
        { body: playersFixture },
      ],
    });
    await aguardarLista();
    await user.click(luta(34));

    const aviso = await screen.findByText("Não achamos nenhum Mago Arcano nessa luta");
    expect(aviso.closest(".notice")).toHaveClass("notice-atencao");
    expect(screen.getByText(/o Warcraft Logs pode ainda estar processando/)).toBeInTheDocument();
    expect(analisar()).toBeDisabled();

    // Lista vazia não é definitiva: escolher a luta de novo refaz a busca.
    await user.click(luta(34));
    await waitFor(() => expect(api.calls(ROTA_JOGADORES)).toHaveLength(2));

    await user.click(await screen.findByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByRole("radio", { name: /Harmonist/ })).toBeInTheDocument();
    expect(api.calls(ROTA_JOGADORES)).toHaveLength(3);
  });

  it("sem violações de acessibilidade com luta e personagem escolhidos", async () => {
    const { container } = abrir({ [ROTA_JOGADORES]: { body: DOIS_MAGOS } });
    await aguardarLista();
    await abrirLuta34();
    await user.click(screen.getByRole("radio", { name: /Reino Dois/ }));

    expect(await axeViolations(container)).toEqual([]);
  });

  it("sem violações de acessibilidade na lista de lutas", async () => {
    const { container } = abrir();
    await aguardarLista();
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("ChooseFight: pré-busca dos eventos (POST /prefetch)", () => {
  // 1 s de espera da tela + folga.
  const PREFETCH_ESPERA = 1100;

  it("só clicar no personagem dispara; marcado sozinho não gasta a pré-busca", async () => {
    const { api } = abrir();
    await aguardarLista();
    const grupo = await abrirLuta34();

    // Único Mago, já marcado: nada é pedido, por mais que o tempo passe.
    expect(within(grupo).getByRole("radio", { name: /Harmonist/ })).toBeChecked();
    await avancar(5000);
    expect(api.calls(ROTA_PREFETCH)).toEqual([]);

    await user.click(within(grupo).getByRole("radio", { name: /Harmonist/ }));
    await avancar(PREFETCH_ESPERA);

    expect(api.calls(ROTA_PREFETCH)).toHaveLength(1);
  });

  it("espera 1 s com a escolha parada e manda o ator da luta no corpo", async () => {
    const { api } = abrir();
    await aguardarLista();
    const grupo = await abrirLuta34();

    await user.click(within(grupo).getByRole("radio", { name: /Harmonist/ }));
    await avancar(500);
    expect(api.calls(ROTA_PREFETCH)).toEqual([]);
    await avancar(600);

    const [chamada] = api.calls(ROTA_PREFETCH);
    expect(chamada.body).toEqual({ actor_id: 455 });
    expect(chamada.authorization).toBeNull();
    // O usuário não vê nada disso: sem aviso, sem erro, a tela segue igual.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("logado, a pré-busca leva o token (conta no limite do plano e na fila do cliente)", async () => {
    const { api } = abrir({}, { logado: true });
    await aguardarLista();
    const grupo = await abrirLuta34();

    await user.click(within(grupo).getByRole("radio", { name: /Harmonist/ }));
    await avancar(PREFETCH_ESPERA);

    expect(api.calls(ROTA_PREFETCH)[0].authorization).toBe("Bearer token-de-teste");
  });

  it("trocar de personagem dentro de 1 s pré-busca só o último", async () => {
    const { api } = abrir({ [ROTA_JOGADORES]: { body: DOIS_MAGOS } });
    await aguardarLista();
    const grupo = await abrirLuta34();

    await user.click(within(grupo).getByRole("radio", { name: /Reino Um.*item level 327/ }));
    await avancar(400);
    await user.click(within(grupo).getByRole("radio", { name: /Reino Dois/ }));
    await avancar(PREFETCH_ESPERA);

    expect(api.calls(ROTA_PREFETCH).map((c) => c.body)).toEqual([{ actor_id: 460 }]);
  });

  it("trocar de luta antes de 1 s cancela a pré-busca", async () => {
    const { api } = abrir({
      "POST /reports/resolve": { body: lista({ fights: comLutas(suportada(50)) }) },
      [`GET /reports/${CODE}/fights/50/players`]: { body: playersFixture },
    });
    await aguardarLista();
    const grupo = await abrirLuta34();

    await user.click(within(grupo).getByRole("radio", { name: /Harmonist/ }));
    await avancar(300);
    await user.click(luta(50));
    await avancar(3000);

    expect(api.calls()).not.toContainEqual(
      expect.objectContaining({ method: "POST", path: expect.stringContaining("/prefetch") }),
    );
  });

  it("clicar de novo no mesmo personagem não repete a pré-busca que deu certo", async () => {
    const { api } = abrir();
    await aguardarLista();
    const grupo = await abrirLuta34();
    const radio = within(grupo).getByRole("radio", { name: /Harmonist/ });

    await user.click(radio);
    await avancar(PREFETCH_ESPERA);
    await user.click(radio);
    await avancar(PREFETCH_ESPERA);

    expect(api.calls(ROTA_PREFETCH)).toHaveLength(1);
  });

  it("falha passageira é silenciosa e um novo clique tenta de novo", async () => {
    const { api } = abrir({
      [ROTA_PREFETCH]: [
        apiError(503, "wcl_unavailable", "O Warcraft Logs está fora do ar."),
        { status: 202, body: { status: "started" } },
      ],
    });
    await aguardarLista();
    const grupo = await abrirLuta34();
    const radio = within(grupo).getByRole("radio", { name: /Harmonist/ });

    await user.click(radio);
    await avancar(PREFETCH_ESPERA);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await user.click(radio);
    await avancar(PREFETCH_ESPERA);

    expect(api.calls(ROTA_PREFETCH)).toHaveLength(2);
  });

  it.each([
    ["teto de pré-buscas", 429, "prefetch_limit", "Muitas pré-buscas. Aguarde alguns minutos."],
    ["plano esgotado", 403, "plan_limit", "Você usou suas 5 análises do mês. Veja o plano Pro."],
  ])(
    "%s: repetir não adianta, então o clique seguinte não pede de novo",
    async (_n, status, codigo, msg) => {
      const { api } = abrir({ [ROTA_PREFETCH]: apiError(status, codigo, msg) });
      await aguardarLista();
      const grupo = await abrirLuta34();
      const radio = within(grupo).getByRole("radio", { name: /Harmonist/ });

      await user.click(radio);
      await avancar(PREFETCH_ESPERA);
      await user.click(radio);
      await avancar(PREFETCH_ESPERA);

      expect(api.calls(ROTA_PREFETCH)).toHaveLength(1);
      // O erro de verdade só aparece na análise: aqui continua tudo normal.
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(analisar()).toBeEnabled();
    },
  );

  it("sem login, depois de usar a demonstração, não pré-busca (a análise está bloqueada)", async () => {
    window.localStorage.setItem("logcoach.demoUsed", "true");
    const { api } = abrir();
    await aguardarLista();
    const grupo = await abrirLuta34();

    await user.click(within(grupo).getByRole("radio", { name: /Harmonist/ }));
    await avancar(3000);

    expect(api.calls(ROTA_PREFETCH)).toEqual([]);
  });
});

describe("ChooseFight: rodar a análise", () => {
  async function prontoParaAnalisar(rotas = {}, opcoes) {
    const retorno = abrir(rotas, opcoes);
    await aguardarLista();
    await abrirLuta34();
    return retorno;
  }
  const passoAtual = () =>
    within(screen.getByRole("list", { name: "Andamento da análise" }))
      .getAllByRole("listitem")
      .find((item) => item.getAttribute("aria-current") === "true");

  it("envia relatório, luta e ator, mostra as etapas e abre o resultado", async () => {
    const { api } = await prontoParaAnalisar();

    await user.click(analisar());

    expect(screen.getByRole("heading", { name: "Analisando sua luta" })).toBeInTheDocument();
    expect(screen.getByText("Nek'zali, a Enrosca-almas · Mítico · Harmonist")).toBeInTheDocument();
    expect(
      screen.getByText("Leva menos de 2 minutos. Você pode deixar esta aba aberta."),
    ).toBeInTheDocument();
    const [chamada] = api.calls("POST /analyses");
    expect(chamada.body).toEqual({ report_code: CODE, fight_id: 34, actor_id: 455 });
    expect(chamada.authorization).toBeNull();
    expect(passoAtual()).toHaveTextContent("Buscando sua luta");

    await avancar(1000);
    expect(passoAtual()).toHaveTextContent("Comparando com os melhores");
    expect(window.location.hash).toBe("");
    await avancar(900);
    // Com o resultado já em mãos, a última etapa fecha e todas aparecem concluídas.
    const etapas = within(screen.getByRole("list", { name: "Andamento da análise" })).getAllByRole(
      "listitem",
    );
    expect(etapas.map((item) => item.className)).toEqual([
      "step step-done",
      "step step-done",
      "step step-done",
    ]);
    expect(window.location.hash).toBe("");

    await avancar(1500);
    expect(window.location.hash).toBe(`#/analise/${analysisFixture.id}`);
  });

  it("a análise lenta fica na última etapa até a resposta chegar", async () => {
    await prontoParaAnalisar({ "POST /analyses": { delay: 6000, ...analiseSalva() } });

    await user.click(analisar());
    await avancar(4000);

    expect(passoAtual()).toHaveTextContent("Coach analisando");
    expect(window.location.hash).toBe("");

    await avancar(3500);
    expect(window.location.hash).toBe(`#/analise/${analysisFixture.id}`);
  });

  it("logado, a análise vai com o token e a sessão continua", async () => {
    const { api } = await prontoParaAnalisar({}, { logado: true });

    await user.click(analisar());
    await avancar(3500);

    expect(api.calls("POST /analyses")[0].authorization).toBe("Bearer token-de-teste");
    expect(lerSessao()).not.toBeNull();
    expect(window.localStorage.getItem("logcoach.demoUsed")).toBeNull();
    expect(window.location.hash).toBe(`#/analise/${analysisFixture.id}`);
  });

  it("guarda o personagem (nome e reino) para marcar na próxima vez", async () => {
    await prontoParaAnalisar();

    await user.click(analisar());

    expect(JSON.parse(window.localStorage.getItem("logcoach.character"))).toEqual({
      name: "Harmonist",
      server: null,
    });
  });

  it("sem login, análise não guardada gasta a demonstração e libera só o convite a criar conta", async () => {
    await prontoParaAnalisar({ "POST /analyses": analiseSalva(false) });

    await user.click(analisar());
    await avancar(3500);

    expect(window.localStorage.getItem("logcoach.demoUsed")).toBe("true");
    expect(window.location.hash).toBe(`#/analise/${analysisFixture.id}`);
  });

  it("com token que não valeu (sessão vencida no meio do uso): sai da conta e gasta a demonstração", async () => {
    await prontoParaAnalisar({ "POST /analyses": analiseSalva(false) }, { logado: true });

    await user.click(analisar());
    await avancar(3500);

    expect(lerSessao()).toBeNull();
    expect(window.localStorage.getItem("logcoach.demoUsed")).toBe("true");
  });

  describe("depois que a demonstração foi usada", () => {
    beforeEach(() => window.localStorage.setItem("logcoach.demoUsed", "true"));

    it("sem login: troca o botão Analisar pelo convite a criar conta, voltando ao relatório", async () => {
      abrir();
      await aguardarLista();
      await abrirLuta34();

      const aviso = screen.getByText("Você já usou a análise de demonstração").closest(".notice");
      expect(aviso).toHaveClass("notice-atencao");
      expect(aviso).toHaveTextContent("até 5 análises por mês");
      expect(within(aviso).getByRole("link", { name: "Criar conta grátis" })).toHaveAttribute(
        "href",
        `#/entrar?modo=cadastro&depois=${encodeURIComponent(`/relatorio/${CODE}`)}`,
      );
      expect(screen.queryByRole("button", { name: "Analisar" })).not.toBeInTheDocument();
    });

    it("com login a análise continua liberada", async () => {
      abrir({}, { logado: true });
      await aguardarLista();
      await abrirLuta34();

      expect(screen.queryByText("Você já usou a análise de demonstração")).toBeNull();
      expect(analisar()).toBeEnabled();
    });
  });

  describe("erros da análise", () => {
    it("limite do plano: mostra a mensagem e leva aos planos", async () => {
      const { api } = await prontoParaAnalisar(
        {
          "POST /analyses": apiError(
            403,
            "plan_limit",
            "Você usou suas 5 análises do mês. Veja o plano Pro.",
          ),
        },
        { logado: true },
      );

      await user.click(analisar());

      const aviso = await screen.findByText("A análise não foi concluída");
      const caixa = aviso.closest(".notice");
      expect(caixa).toHaveAttribute("role", "alert");
      expect(caixa).toHaveTextContent("Você usou suas 5 análises do mês. Veja o plano Pro.");
      expect(within(caixa).getByRole("link", { name: "Ver planos" })).toHaveAttribute(
        "href",
        "#/planos",
      );
      // Repetir não resolve: o botão continua sendo Analisar, e a lista segue na tela.
      expect(analisar()).toHaveTextContent("Analisar");
      expect(screen.getByRole("radio", { name: /Harmonist/ })).toBeChecked();
      expect(api.calls("POST /analyses")).toHaveLength(1);
    });

    it("Warcraft Logs fora do ar: o botão vira 'Tentar de novo' e repete o pedido", async () => {
      const { api } = await prontoParaAnalisar({
        "POST /analyses": [
          apiError(503, "wcl_unavailable", "O Warcraft Logs não respondeu. Tente em instantes."),
          analiseSalva(),
        ],
      });

      await user.click(analisar());

      const caixa = (await screen.findByText("A análise não foi concluída")).closest(".notice");
      expect(caixa).toHaveTextContent("O Warcraft Logs não respondeu. Tente em instantes.");
      expect(within(caixa).queryByRole("link", { name: "Ver planos" })).toBeNull();
      expect(analisar()).toHaveTextContent("Tentar de novo");

      await user.click(analisar());
      await avancar(3500);

      expect(api.calls("POST /analyses")).toHaveLength(2);
      expect(api.calls("POST /analyses")[1].body).toEqual(api.calls("POST /analyses")[0].body);
      expect(window.location.hash).toBe(`#/analise/${analysisFixture.id}`);
    });

    it.each([
      [
        "erro nosso (500 sem código)",
        { status: 500, body: "<html>erro</html>", html: true },
        "Erro inesperado no LogCoach.",
      ],
      ["rede fora", new TypeError("Failed to fetch"), "O servidor do LogCoach não respondeu."],
      [
        "unexpected_error do motor",
        apiError(500, "unexpected_error", "Erro inesperado no LogCoach. O problema é nosso."),
        "Erro inesperado no LogCoach.",
      ],
    ])("%s: mostra a mensagem e oferece tentar de novo", async (_nome, resposta, texto) => {
      await prontoParaAnalisar({ "POST /analyses": resposta });

      await user.click(analisar());

      expect(await screen.findByRole("alert")).toHaveTextContent(texto);
      expect(analisar()).toHaveTextContent("Tentar de novo");
    });

    it("sem dados para comparar (analysis_not_available): mostra a mensagem, sem 'Tentar de novo'", async () => {
      await prontoParaAnalisar({
        "POST /analyses": apiError(
          503,
          "analysis_not_available",
          "Ainda não há tops para esse chefe, dificuldade e faixa de item level.",
        ),
      });

      await user.click(analisar());

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Ainda não há tops para esse chefe",
      );
      expect(analisar()).toHaveTextContent("Analisar");
    });

    it("escolher outro personagem depois do erro limpa o aviso", async () => {
      abrir({
        [ROTA_JOGADORES]: { body: DOIS_MAGOS },
        "POST /analyses": apiError(503, "wcl_unavailable", "O Warcraft Logs não respondeu."),
      });
      await aguardarLista();
      await abrirLuta34();
      await user.click(screen.getByRole("radio", { name: /Reino Dois/ }));
      await user.click(analisar());
      await screen.findByText("A análise não foi concluída");

      await user.click(screen.getByRole("radio", { name: /Outra Maga/ }));

      expect(screen.queryByText("A análise não foi concluída")).not.toBeInTheDocument();
      expect(analisar()).toHaveTextContent("Analisar");
    });
  });
});

describe("ChooseFight: atualizar a lista de lutas (botão)", () => {
  it("lista nova com uma luta a mais: mostra as lutas e diz '1 luta nova'", async () => {
    const { api } = abrir({
      "POST /reports/resolve": [
        { body: lista() },
        { body: lista({ n: 30, fights: comLutas(suportada(50)) }) },
      ],
    });
    await aguardarLista();

    await user.click(atualizar());

    expect(await screen.findByText(/· 1 luta nova/)).toBeInTheDocument();
    expect(luta(50)).toBeInTheDocument();
    expect(
      screen.getByText(`Lista de ${hora(lista({ n: 30 }).fetched_at)}`, { exact: false }),
    ).toBeInTheDocument();
    expect(chamadasResolve(api)).toBe(2);
    expect(api.calls("POST /reports/resolve")[1].body).toEqual({
      url: `https://www.warcraftlogs.com/reports/${CODE}`,
    });
  });

  it("mostra 'Atualizando…' e ignora cliques enquanto a busca não termina", async () => {
    const { api } = abrir({
      "POST /reports/resolve": [{ body: lista() }, { delay: 2000, body: lista({ n: 5 }) }],
    });
    await aguardarLista();

    await user.click(atualizar());
    expect(screen.getByRole("button", { name: "Atualizando…" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    await user.click(screen.getByRole("button", { name: "Atualizando…" }));
    await avancar(2500);

    expect(chamadasResolve(api)).toBe(2);
    expect(screen.getByRole("button", { name: "Atualizar lutas" })).toBeInTheDocument();
  });

  it.each([
    [
      "mesma hora de leitura (travou em 8 s no servidor)",
      () => lista(),
      "A lista já está atualizada",
    ],
    ["lista lida de novo, sem mudanças", () => lista({ n: 20 }), "Nenhuma luta nova"],
    [
      "duas lutas novas",
      () => lista({ n: 20, fights: comLutas(suportada(50), suportada(51)) }),
      "2 lutas novas",
    ],
    [
      "uma luta passou a poder ser analisada",
      () => {
        const fights = structuredClone(reportFixture.fights);
        Object.assign(fights[2], {
          supported: true,
          unsupported_code: null,
          unsupported_reason: null,
        });
        return lista({ n: 20, fights });
      },
      "1 luta liberada para análise",
    ],
    [
      "luta nova e outra liberada",
      () => {
        const fights = structuredClone(reportFixture.fights);
        Object.assign(fights[2], {
          supported: true,
          unsupported_code: null,
          unsupported_reason: null,
        });
        return lista({ n: 20, fights: [...fights, suportada(50)] });
      },
      "1 luta nova e 1 liberada para análise",
    ],
  ])("resultado do clique: %s", async (_nome, nova, texto) => {
    abrir({ "POST /reports/resolve": [{ body: lista() }, { body: nova() }] });
    await aguardarLista();

    await user.click(atualizar());

    expect(await screen.findByText(new RegExp(`· ${texto}$`))).toBeInTheDocument();
  });

  it("falha no clique: avisa com a mensagem do servidor e mantém a lista que estava na tela", async () => {
    abrir({
      "POST /reports/resolve": [
        { body: lista() },
        apiError(503, "wcl_unavailable", "O Warcraft Logs está fora do ar."),
      ],
    });
    await aguardarLista();

    await user.click(atualizar());

    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent("Não deu para atualizar as lutas");
    expect(aviso).toHaveTextContent("O Warcraft Logs está fora do ar.");
    expect(luta(34)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Atualizar lutas" })).toBeInTheDocument();
  });

  it("o aviso de erro some no próximo clique que der certo", async () => {
    abrir({
      "POST /reports/resolve": [
        { body: lista() },
        apiError(503, "wcl_unavailable", "O Warcraft Logs está fora do ar."),
        { body: lista({ n: 9 }) },
      ],
    });
    await aguardarLista();
    await user.click(atualizar());
    await screen.findByRole("alert");

    await user.click(atualizar());

    expect(await screen.findByText(/· Nenhuma luta nova/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("ChooseFight: lista guardada (Warcraft Logs fora do ar)", () => {
  it("abre com a lista guardada, a hora dela e o motivo do servidor", async () => {
    abrir({ "POST /reports/resolve": { body: guardada() } });
    await aguardarLista();

    const aviso = screen.getByText("Não deu para atualizar a lista").closest(".notice");
    expect(aviso).toHaveClass("notice-atencao");
    expect(aviso).toHaveTextContent("O Warcraft Logs está fora do ar.");
    expect(aviso).toHaveTextContent(`Mostrando a lista de ${hora(guardada().fetched_at)}.`);
    // A lista guardada continua utilizável.
    expect(luta(34)).not.toHaveAttribute("aria-disabled");
  });

  it("mostra a causa quando o erro é do LogCoach", async () => {
    abrir({
      "POST /reports/resolve": {
        body: guardada({
          stale_code: "unexpected_error",
          stale_message: "Erro inesperado no LogCoach. O problema é nosso.",
        }),
      },
    });
    await aguardarLista();

    expect(screen.getByText("Não deu para atualizar a lista").closest(".notice")).toHaveTextContent(
      "Erro inesperado no LogCoach. O problema é nosso.",
    );
  });

  it("clique sem sucesso responde com a hora; o seguinte diz 'Ainda sem resposta'", async () => {
    abrir({ "POST /reports/resolve": [{ body: lista() }, { body: guardada() }] });
    await aguardarLista();

    // A lista estava em dia e o clique cai na lista guardada: "Sem resposta".
    await user.click(atualizar());
    expect(
      await screen.findByText(/· Sem resposta do Warcraft Logs \(\d\d:\d\d:\d\d\)/),
    ).toBeInTheDocument();
    expect(screen.getByText("Não deu para atualizar a lista")).toBeInTheDocument();

    await avancar(2000);
    await user.click(atualizar());
    expect(
      await screen.findByText(/· Ainda sem resposta do Warcraft Logs \(\d\d:\d\d:\d\d\)/),
    ).toBeInTheDocument();
  });

  it("abrir já na lista guardada e clicar: é 'Ainda sem resposta' desde o primeiro clique", async () => {
    abrir({ "POST /reports/resolve": { body: guardada() } });
    await aguardarLista();

    await user.click(atualizar());

    expect(await screen.findByText(/· Ainda sem resposta do Warcraft Logs/)).toBeInTheDocument();
  });

  it.each(["unexpected_error", "query_limit"])(
    "com %s o texto do clique é neutro, sem culpar o Warcraft Logs",
    async (codigo) => {
      abrir({
        "POST /reports/resolve": [
          { body: lista() },
          { body: guardada({ stale_code: codigo, stale_message: "Mensagem do servidor." }) },
        ],
      });
      await aguardarLista();

      await user.click(atualizar());

      expect(
        await screen.findByText(/· Não deu para atualizar \(\d\d:\d\d:\d\d\)/),
      ).toBeInTheDocument();
      expect(screen.queryByText(/Sem resposta do Warcraft Logs/)).not.toBeInTheDocument();
    },
  );

  it("quando o Warcraft Logs volta, o aviso da lista guardada sai", async () => {
    abrir({
      "POST /reports/resolve": [{ body: guardada() }, { body: lista({ n: 60 }) }],
    });
    await aguardarLista();
    expect(screen.getByText("Não deu para atualizar a lista")).toBeInTheDocument();

    await user.click(atualizar());

    expect(await screen.findByText(/· Nenhuma luta nova/)).toBeInTheDocument();
    expect(screen.queryByText("Não deu para atualizar a lista")).not.toBeInTheDocument();
  });

  it("luta que estava subindo não é afirmada como subindo: 'Sem atualização' e o texto no passado", async () => {
    abrir({
      "POST /reports/resolve": { body: guardada({ fights: comLutas(subindo(50)) }) },
    });
    await aguardarLista();

    const botao = luta(50);
    expect(botao).toHaveTextContent("Sem atualização");
    expect(botao).not.toHaveTextContent("Subindo…");
    expect(botao).toHaveAccessibleDescription(
      "Ela estava subindo na última consulta. Clique em Atualizar lutas para ver se já terminou.",
    );
  });
});

describe("ChooseFight: log ao vivo e atualização automática", () => {
  const ao_vivo = (n = 0, extra = []) => lista({ n, fights: comLutas(subindo(50), ...extra) });

  it("sem luta subindo e sem atividade recente, não atualiza sozinha", async () => {
    const { api } = abrir();
    await aguardarLista();

    await avancar(15 * MIN);

    expect(chamadasResolve(api)).toBe(1);
    expect(screen.queryByText(/Acompanhando o log ao vivo/)).not.toBeInTheDocument();
  });

  it("luta subindo: mostra o selo, o motivo, avisa do acompanhamento e não deixa escolher", async () => {
    const { api } = abrir({ "POST /reports/resolve": { body: ao_vivo() } });
    await aguardarLista();

    const botao = luta(50);
    expect(botao).toHaveTextContent("Subindo…");
    expect(botao).toHaveAttribute("aria-disabled", "true");
    expect(botao).toHaveAccessibleDescription(MOTIVO_SUBINDO);
    expect(
      screen.getByText("Acompanhando o log ao vivo", { exact: false }).closest("p"),
    ).toHaveTextContent(
      "Acompanhando o log ao vivo (luta subindo para o Warcraft Logs): próxima atualização em 4 min (ou clique em “Atualizar lutas”).",
    );

    await user.click(botao);
    expect(api.calls(`GET /reports/${CODE}/fights/50/players`)).toEqual([]);
  });

  it("log recebendo dados nos últimos 10 min (live) já liga a espera pelo próximo pull", async () => {
    abrir({ "POST /reports/resolve": { body: lista({ live: true }) } });
    await aguardarLista();

    expect(screen.getByText("(esperando o próximo pull)")).toBeInTheDocument();
  });

  it("a contagem regressiva anda em minutos", async () => {
    abrir({ "POST /reports/resolve": { body: ao_vivo() } });
    await aguardarLista();

    await avancar(2 * MIN + 5000);

    expect(screen.getByText(/próxima atualização em 2 min/)).toBeInTheDocument();
  });

  it("depois de 4 min refaz a lista sozinha e anuncia luta nova", async () => {
    const { api } = abrir({
      "POST /reports/resolve": [{ body: ao_vivo() }, { body: ao_vivo(240, [suportada(51)]) }],
    });
    await aguardarLista();

    await avancar(4 * MIN - 5000);
    expect(chamadasResolve(api)).toBe(1);
    await avancar(6000);

    await waitFor(() => expect(chamadasResolve(api)).toBe(2));
    expect(await screen.findByText(/· 1 luta nova/)).toBeInTheDocument();
    expect(luta(51)).toBeInTheDocument();
  });

  it("mostra 'buscando agora…' durante a busca automática", async () => {
    abrir({
      "POST /reports/resolve": [{ body: ao_vivo() }, { delay: 3000, body: ao_vivo(1) }],
    });
    await aguardarLista();

    await avancar(4 * MIN + 500);

    expect(screen.getByText(/buscando agora…/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Atualizando…" })).toBeInTheDocument();
    await avancar(3500);
    expect(screen.queryByText(/buscando agora…/)).not.toBeInTheDocument();
  });

  it("automática sem novidade é silenciosa (não escreve 'Nenhuma luta nova')", async () => {
    const { api } = abrir({
      "POST /reports/resolve": [{ body: ao_vivo() }, { body: ao_vivo(240) }],
    });
    await aguardarLista();

    await avancar(4 * MIN + 500);

    await waitFor(() => expect(chamadasResolve(api)).toBe(2));
    expect(screen.queryByText(/Nenhuma luta nova/)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("luta que terminou de subir vira escolhível, e o acompanhamento continua", async () => {
    const pronta = { ...suportada(50), duration_s: 330 };
    const { api } = abrir({
      "POST /reports/resolve": [
        { body: ao_vivo() },
        { body: lista({ n: 240, fights: comLutas(pronta) }) },
      ],
    });
    await aguardarLista();

    await avancar(4 * MIN + 500);

    await waitFor(() => expect(chamadasResolve(api)).toBe(2));
    expect(await screen.findByText(/· 1 luta liberada para análise/)).toBeInTheDocument();
    expect(luta(50)).not.toHaveAttribute("aria-disabled");
    expect(luta(50)).toHaveTextContent("Mítico · luta 50 · 5:30");
    expect(screen.getByText("(esperando o próximo pull)")).toBeInTheDocument();
  });

  it("falha da automática não mostra erro, mas conta como tentativa sem novidade", async () => {
    const { api } = abrir({
      "POST /reports/resolve": [
        { body: ao_vivo() },
        apiError(503, "wcl_unavailable", "O Warcraft Logs está fora do ar."),
      ],
    });
    await aguardarLista();

    await avancar(4 * MIN + 500);

    await waitFor(() => expect(chamadasResolve(api)).toBe(2));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(luta(34)).toBeInTheDocument();
  });

  it("para depois de 3 automáticas seguidas sem novidade e avisa", async () => {
    const { api } = abrir({
      "POST /reports/resolve": [{ body: ao_vivo() }, { body: ao_vivo(1) }],
    });
    await aguardarLista();

    for (let i = 1; i <= 3; i += 1) {
      await avancar(4 * MIN + 500);
      await waitFor(() => expect(chamadasResolve(api)).toBe(1 + i));
    }

    const aviso = await screen.findByText("Atualização automática parada:");
    expect(aviso.closest("p")).toHaveTextContent(
      "nada mudou nas últimas 3 atualizações (cerca de 12 min). “Atualizar lutas” confere de novo e volta a acompanhar.",
    );
    await avancar(20 * MIN);
    expect(chamadasResolve(api)).toBe(4);
    // Sem acompanhamento, a luta que subia deixa de ser afirmada como subindo.
    expect(luta(50)).toHaveTextContent("Sem atualização");
  });

  it("novidade no meio zera a contagem das paradas", async () => {
    const respostas = [
      { body: ao_vivo() },
      { body: ao_vivo(1) }, // sem novidade (1)
      { body: ao_vivo(2) }, // sem novidade (2)
      { body: ao_vivo(3, [suportada(51)]) }, // luta nova: zera
      { body: ao_vivo(4, [suportada(51)]) }, // sem novidade (1)
      { body: ao_vivo(5, [suportada(51)]) }, // sem novidade (2)
      { body: ao_vivo(6, [suportada(51)]) }, // sem novidade (3): para
    ];
    const { api } = abrir({ "POST /reports/resolve": respostas });
    await aguardarLista();

    for (let i = 1; i <= 5; i += 1) {
      await avancar(4 * MIN + 500);
      await waitFor(() => expect(chamadasResolve(api)).toBe(1 + i));
    }
    // 5 automáticas, mas só 2 sem novidade desde a luta nova: segue acompanhando.
    expect(screen.queryByText("Atualização automática parada:")).not.toBeInTheDocument();

    await avancar(4 * MIN + 500);
    await waitFor(() => expect(chamadasResolve(api)).toBe(7));
    expect(await screen.findByText("Atualização automática parada:")).toBeInTheDocument();
  });

  it("'Atualizar lutas' depois da parada volta a acompanhar e reinicia a contagem", async () => {
    const { api } = abrir({
      "POST /reports/resolve": [{ body: ao_vivo() }, { body: ao_vivo(1) }],
    });
    await aguardarLista();
    for (let i = 1; i <= 3; i += 1) {
      await avancar(4 * MIN + 500);
      await waitFor(() => expect(chamadasResolve(api)).toBe(1 + i));
    }
    await screen.findByText("Atualização automática parada:");

    await user.click(atualizar());

    await waitFor(() => expect(chamadasResolve(api)).toBe(5));
    expect(screen.queryByText("Atualização automática parada:")).not.toBeInTheDocument();
    expect(screen.getByText("Acompanhando o log ao vivo", { exact: false })).toBeInTheDocument();
    expect(luta(50)).toHaveTextContent("Subindo…");
    await avancar(4 * MIN + 500);
    await waitFor(() => expect(chamadasResolve(api)).toBe(6));
  });

  it("clicar em 'Atualizar lutas' reinicia a espera de 4 min", async () => {
    const { api } = abrir({ "POST /reports/resolve": { body: ao_vivo() } });
    await aguardarLista();

    await avancar(3 * MIN);
    await user.click(atualizar());
    await waitFor(() => expect(chamadasResolve(api)).toBe(2));
    await avancar(3 * MIN);
    // 6 min desde a abertura, mas só 3 desde o clique: nada automático ainda.
    expect(chamadasResolve(api)).toBe(2);

    await avancar(1 * MIN + 5000);
    await waitFor(() => expect(chamadasResolve(api)).toBe(3));
  });

  it("com a aba escondida não busca; ao voltar, depois do prazo, atualiza na hora", async () => {
    const { api } = abrir({ "POST /reports/resolve": { body: ao_vivo() } });
    await aguardarLista();

    esconderAba();
    await avancar(5 * MIN);
    expect(chamadasResolve(api)).toBe(1);

    mostrarAba();

    await waitFor(() => expect(chamadasResolve(api)).toBe(2));
  });

  it("voltar para a aba antes do prazo não busca", async () => {
    const { api } = abrir({ "POST /reports/resolve": { body: ao_vivo() } });
    await aguardarLista();

    esconderAba();
    await avancar(1 * MIN);
    mostrarAba();
    await avancar(1000);

    expect(chamadasResolve(api)).toBe(1);
  });

  it("luta com upload pausado: selo próprio, motivo do servidor e não liga o acompanhamento", async () => {
    const { api } = abrir({
      "POST /reports/resolve": { body: lista({ fights: comLutas(pausada(52)) }) },
    });
    await aguardarLista();

    const botao = luta(52);
    expect(botao).toHaveTextContent("Upload pausado");
    expect(botao).toHaveAttribute("aria-disabled", "true");
    expect(botao).toHaveAccessibleDescription(
      "O upload dessa luta parou no meio. Envie o log de novo.",
    );
    expect(screen.queryByText(/Acompanhando o log ao vivo/)).not.toBeInTheDocument();
    await user.click(botao);
    expect(api.calls(`GET /reports/${CODE}/fights/52/players`)).toEqual([]);
    await avancar(10 * MIN);
    expect(chamadasResolve(api)).toBe(1);
  });

  it("sem violações de acessibilidade com o log ao vivo na tela", async () => {
    const { container } = abrir({ "POST /reports/resolve": { body: ao_vivo() } });
    await aguardarLista();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("sem violações de acessibilidade com a lista guardada na tela", async () => {
    const { container } = abrir({
      "POST /reports/resolve": { body: guardada({ fights: comLutas(subindo(50)) }) },
    });
    await aguardarLista();
    expect(await axeViolations(container)).toEqual([]);
  });
});
