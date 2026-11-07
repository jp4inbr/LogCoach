import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import AuthProvider from "../components/AuthProvider.jsx";
import { axeViolations } from "../test/axe.js";
import analise from "../test/fixtures/analysis.json";
import { apiError, mockApi, setSession } from "../test/mockApi.js";
import Result from "./Result.jsx";

const ID = analise.id;

// Cópia da resposta real para derivar variações sem mexer na fixture.
function variacao(ajustar) {
  const copia = structuredClone(analise);
  ajustar?.(copia);
  return copia;
}

function renderResult(corpo = analise, { id = ID, logado = false } = {}) {
  if (logado) setSession();
  const api = mockApi({
    [`GET /analyses/${id}`]: corpo instanceof Error || corpo.status ? corpo : { body: corpo },
    "GET /me": { body: {} },
  });
  const view = render(
    <AuthProvider>
      <Result id={id} />
    </AuthProvider>,
  );
  return { api, ...view };
}

async function aberta(corpo, opcoes) {
  const view = renderResult(corpo, opcoes);
  await screen.findByRole("heading", { level: 1 });
  return view;
}

// Tabela (entre várias com o mesmo nome acessível) que tem a coluna pedida.
const tabelaComColuna = (coluna, nome) =>
  screen
    .getAllByRole("table", nome ? { name: nome } : {})
    .find((tabela) => within(tabela).queryByRole("columnheader", { name: coluna }));

const aba = (nome) => screen.getByRole("tab", { name: nome });

describe("Result", () => {
  describe("carregamento e cabeçalho", () => {
    it("mostra o carregamento e depois a análise pedida pelo id", async () => {
      const { api } = renderResult();

      expect(screen.getByText("Carregando a análise…")).toBeInTheDocument();
      expect(
        await screen.findByRole("heading", { level: 1, name: "Nek'zali, a Enrosca-almas" }),
      ).toBeInTheDocument();
      expect(api.calls(`GET /analyses/${ID}`)).toHaveLength(1);
      // Sem login, o pedido vai sem token.
      expect(api.calls(`GET /analyses/${ID}`)[0].authorization).toBeNull();
    });

    it("com login, o pedido leva o token da sessão", async () => {
      const { api } = await aberta(analise, { logado: true });
      expect(api.calls(`GET /analyses/${ID}`)[0].authorization).toBe("Bearer token-de-teste");
    });

    it("mostra dificuldade, resultado da luta, tempo, jogador, spec e item level", async () => {
      await aberta();

      expect(screen.getByText("Mítico · Kill em 6:56")).toBeInTheDocument();
      expect(screen.getByText("Harmonist · Mago Arcano · item level 327")).toBeInTheDocument();
    });

    it("wipe e jogador com reino aparecem como o usuário espera", async () => {
      await aberta(
        variacao((a) => {
          a.result.fight.kill = false;
          a.result.player.server = "Reino Teste";
        }),
      );

      expect(screen.getByText("Mítico · Wipe em 6:56")).toBeInTheDocument();
      expect(
        screen.getByText("Harmonist (Reino Teste) · Mago Arcano · item level 327"),
      ).toBeInTheDocument();
    });

    it("o link 'Escolher outra luta' volta para o relatório da análise", async () => {
      await aberta();
      expect(screen.getByRole("link", { name: "← Escolher outra luta" })).toHaveAttribute(
        "href",
        "#/relatorio/XhrmBaYkGCAQjH2D",
      );
    });
  });

  describe("números do resumo", () => {
    it("mostra DPS, média do bracket, diferença e tempo ativo formatados em pt-BR", async () => {
      await aberta();

      const bloco = (rotulo) =>
        screen
          .getAllByText(rotulo, { exact: false })
          .map((el) => el.closest(".stat"))
          .find(Boolean);
      expect(within(bloco("Seu DPS")).getByText("226 mil")).toBeInTheDocument();
      expect(within(bloco("Média do")).getByText("266 mil")).toBeInTheDocument();
      expect(bloco("Os tops fizeram")).toHaveTextContent("Os tops fizeram+18% de dano");
      expect(bloco("Os tops fizeram")).toHaveClass("stat-down");
      expect(bloco("Tempo ativo")).toHaveTextContent("98,6% (tops 99,7%)");
    });

    it("análise antiga sem `gap` mostra a diferença do DPS em vez do bloco novo", async () => {
      await aberta(
        variacao((a) => {
          a.result.gap = null;
        }),
      );

      const bloco = screen.getByText("Diferença").closest(".stat");
      expect(bloco).toHaveTextContent("−15,2%");
      expect(bloco).toHaveClass("stat-down");
      expect(screen.queryByText("Os tops fizeram")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("De onde vem a diferença para os tops")).toBeNull();
    });

    it("jogador acima dos tops: texto e cor a favor", async () => {
      await aberta(
        variacao((a) => {
          a.result.gap = { total_pct: -4.2, mistakes_pct: 1, luck_pct: -2, unexplained_pct: -3.2 };
        }),
      );

      expect(screen.getByText("Os tops fizeram").closest(".stat")).toHaveClass("stat-up");
      const gap = screen.getByLabelText("De onde vem a diferença para os tops");
      expect(gap).toHaveTextContent("Você fez 4,2% mais dano que a média dos tops.");
      // Parte negativa = a favor do jogador, escrita assim (não como erro).
      expect(gap).toHaveTextContent("Sorte com a Seta Prismática (a seu favor)−2%");
      expect(gap).toHaveTextContent("Não explicado (a seu favor)−3,2%");
    });

    it("de onde vem a diferença: erros + sorte + não explicado, em % do dano", async () => {
      await aberta();

      const gap = screen.getByLabelText("De onde vem a diferença para os tops");
      expect(gap).toHaveTextContent("Os tops fizeram 18% mais dano que você.");
      const itens = within(gap).getAllByRole("listitem");
      expect(itens).toHaveLength(3);
      expect(itens[0]).toHaveTextContent("Erros6,6%");
      expect(itens[1]).toHaveTextContent("Azar com a Seta Prismática9,5%");
      expect(itens[2]).toHaveTextContent("Não explicado1,9%");
      expect(gap).toHaveTextContent("Em % do seu próprio dano na luta.");
    });
  });

  describe("coach e erros (aba Resumo)", () => {
    it("motor sem IA: avisa que o coach vem na próxima versão", async () => {
      await aberta();
      expect(screen.getByText("Explicação do coach em breve")).toBeInTheDocument();
      expect(screen.queryByText("Resumo do coach")).not.toBeInTheDocument();
    });

    it("com o coach disponível mostra o resumo dele", async () => {
      await aberta(
        variacao((a) => {
          a.result.coach = { available: true, headline: "Priorize chegar na Alma com Salvo alto." };
        }),
      );

      expect(screen.getByText("Resumo do coach")).toBeInTheDocument();
      expect(screen.getByText("Priorize chegar na Alma com Salvo alto.")).toBeInTheDocument();
      expect(screen.queryByText("Explicação do coach em breve")).not.toBeInTheDocument();
    });

    it("IA fora do ar em análise de exemplo: avisa que só valem as regras", async () => {
      await aberta(
        variacao((a) => {
          a.result.source = "exemplo";
        }),
      );

      expect(screen.getByText("Explicação do coach indisponível agora")).toBeInTheDocument();
      expect(
        screen.getByText(/Os erros abaixo vêm só das regras, que são calculadas direto do log/),
      ).toBeInTheDocument();
    });

    it("lista os erros das regras do maior para o menor impacto, numerados", async () => {
      await aberta();

      const cards = screen.getAllByRole("article");
      const titulos = cards.map(
        (card) => within(card).getByRole("heading", { level: 3 }).textContent,
      );
      // Os 7 erros de regra na ordem que o motor mandou, e a hipótese separada, sem número.
      expect(titulos.slice(0, 3)).toEqual([
        "Entrada na Alma Arcana com pouco Salvo",
        "Impactos Arcanos demais dentro do Surto",
        "Tempo ativo abaixo dos tops",
      ]);
      expect(titulos).toHaveLength(8);
      expect(within(cards[0]).getByText("1")).toBeInTheDocument();
      expect(within(cards[1]).getByText("2")).toBeInTheDocument();
    });

    it("cada erro mostra gravidade, custo, o que fazer e os números", async () => {
      await aberta();

      const [primeiro] = screen.getAllByRole("article");
      expect(primeiro).toHaveTextContent("✕ Erro");
      expect(primeiro).toHaveTextContent("Custou cerca de 2,7% do seu dano");
      expect(within(primeiro).getByText("O que fazer")).toBeInTheDocument();
      expect(primeiro).toHaveTextContent("Chegue na Alma Arcana com 20 de Salvo ou mais.");
      const linha = within(primeiro).getByRole("row", { name: /Entradas na Alma Arcana/ });
      expect(linha).toHaveTextContent("2 de 5 (0, 20, 1, 18, 22)9 de 43");
    });

    it("erro sem custo calculado diz isso em vez de inventar um número", async () => {
      await aberta();

      const dano = screen
        .getAllByRole("article")
        .find((card) => card.textContent.includes("Dano evitável recebido"));
      expect(dano).toHaveTextContent(
        "Sem custo em dano calculado (risco de morte ou efeito indireto)",
      );
      expect(dano).not.toHaveTextContent("Custou cerca de");
    });

    it("atenção e erro têm marcação diferente", async () => {
      await aberta();

      const cards = screen.getAllByRole("article");
      expect(cards[0]).toHaveClass("mistake-erro");
      expect(cards[1]).toHaveClass("mistake-atencao");
      expect(cards[1]).toHaveTextContent("! Atenção");
    });

    it("a hipótese fica numa seção própria, marcada como não confirmada", async () => {
      await aberta();

      expect(screen.getByRole("heading", { name: "O que as regras não explicam" })).toBeVisible();
      expect(screen.getByText(/pistas, não erros confirmados/)).toBeInTheDocument();
      const hipotese = screen
        .getAllByRole("article")
        .find((card) => card.textContent.includes("(hipótese)"));
      expect(hipotese).toHaveTextContent("Hipótese");
      expect(hipotese).toHaveTextContent("As regras não explicam cerca de 1,9 pontos da diferença");
      expect(hipotese).not.toHaveTextContent("Custou cerca de");
      // Hipótese não entra na numeração dos erros confirmados.
      expect(within(hipotese).queryByText(/^\d+$/)).not.toBeInTheDocument();
    });

    it("sem erros: parabeniza e não mostra a seção de hipóteses", async () => {
      await aberta(
        variacao((a) => {
          a.result.mistakes = [];
        }),
      );

      expect(screen.getByText("Nenhum erro encontrado")).toBeInTheDocument();
      expect(screen.getByText("Sua luta bateu com os melhores em todas as regras.")).toBeVisible();
      expect(screen.queryByRole("article")).not.toBeInTheDocument();
      expect(screen.queryByText("O que as regras não explicam")).not.toBeInTheDocument();
    });

    it("a pergunta ao coach aparece desabilitada, como recurso do plano Pro", async () => {
      await aberta();

      expect(screen.getByLabelText("Pergunte ao coach sobre um erro")).toBeDisabled();
      expect(screen.getByRole("button", { name: "Perguntar" })).toBeDisabled();
      expect(screen.getByText("Em breve, no plano Pro.")).toBeInTheDocument();
    });
  });

  describe("avisos de dados", () => {
    it("resultado de exemplo tem o aviso amarelo", async () => {
      await aberta(
        variacao((a) => {
          a.result.source = "exemplo";
        }),
      );

      const aviso = screen.getByText("Resultado de exemplo").closest(".notice");
      expect(aviso).toHaveClass("notice-atencao");
    });

    it("resultado do motor não tem o aviso de exemplo", async () => {
      await aberta();
      expect(screen.queryByText("Resultado de exemplo")).not.toBeInTheDocument();
    });

    it("comparação com a cópia de exemplo dos tops é avisada", async () => {
      await aberta();
      expect(screen.getByText("Comparação com tops de exemplo")).toBeInTheDocument();
    });

    it("comparação com tops reais não tem avisos de tops de exemplo nem guardados", async () => {
      await aberta(
        variacao((a) => {
          a.result.comparison.sample = false;
        }),
      );

      expect(screen.queryByText("Comparação com tops de exemplo")).not.toBeInTheDocument();
      expect(screen.queryByText("Comparação com tops guardados")).not.toBeInTheDocument();
    });

    it("tops guardados há mais de 24 h (Warcraft Logs fora do ar) são avisados", async () => {
      await aberta(
        variacao((a) => {
          a.result.comparison.sample = false;
          a.result.comparison.stale = true;
        }),
      );

      expect(screen.getByText("Comparação com tops guardados")).toBeInTheDocument();
      expect(screen.getByText(/O ranking de hoje pode estar um pouco diferente/)).toBeVisible();
    });

    it("jogador entre os 10 melhores: explica que o 11º entrou no lugar (RF21)", async () => {
      await aberta(
        variacao((a) => {
          a.result.comparison.player_in_top = true;
        }),
      );

      expect(screen.getByText("Você está entre os 10 melhores do seu bracket")).toBeInTheDocument();
      expect(screen.getByText(/entrou o 11º colocado/)).toBeInTheDocument();
    });

    it("análise não guardada (sem login): convida a criar conta", async () => {
      await aberta();

      expect(screen.getByText("Esta análise não foi guardada")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Criar conta grátis" })).toHaveAttribute(
        "href",
        "#/entrar?modo=cadastro",
      );
    });

    it("análise guardada na conta não mostra o convite", async () => {
      await aberta(
        variacao((a) => {
          a.saved = true;
        }),
        { logado: true },
      );

      expect(screen.queryByText("Esta análise não foi guardada")).not.toBeInTheDocument();
    });
  });

  describe("quem foi comparado (RF25)", () => {
    const comNomes = () =>
      variacao((a) => {
        a.result.comparison.players.forEach((jogador, i) => {
          jogador.name = `Mago Teste ${i + 1}`;
          jogador.server = "Reino Teste";
        });
      });

    it("mostra a lista só com pseudônimos, item level e DPS", async () => {
      await aberta();

      const tabela = screen.getByRole("table", { name: /Top 10 do bracket 326–328/ });
      const linhas = within(tabela).getAllByRole("row");
      expect(linhas).toHaveLength(11); // cabeçalho + 10
      expect(linhas[1]).toHaveTextContent("1ºTop 1328279 mil");
      expect(linhas[10]).toHaveTextContent("10ºTop 10326259 mil");
      expect(screen.getByText("Top 10 do bracket 326–328 · 10 jogadores")).toBeInTheDocument();
    });

    it("sem nomes reais (dados de exemplo) o botão fica desligado e explica o motivo", async () => {
      await aberta();

      const botao = screen.getByRole("button", { name: "Mostrar nomes" });
      expect(botao).toBeDisabled();
      expect(botao).toHaveAccessibleDescription("Nomes reais indisponíveis nos dados de exemplo.");
    });

    it("com nomes reais eles ficam ocultos por padrão", async () => {
      await aberta(comNomes());

      expect(screen.queryByText(/Mago Teste/)).not.toBeInTheDocument();
      expect(screen.getByText("Top 1")).toBeInTheDocument();
      const botao = screen.getByRole("button", { name: "Mostrar nomes" });
      expect(botao).toBeEnabled();
      expect(botao).toHaveAttribute("aria-pressed", "false");
      expect(
        screen.getByText(
          "Os nomes dos outros jogadores ficam ocultos por padrão. Você sempre aparece com o seu.",
        ),
      ).toBeInTheDocument();
    });

    it("o jogador analisado nunca é ocultado", async () => {
      await aberta(comNomes());
      expect(screen.getByText(/Harmonist · Mago Arcano/)).toBeInTheDocument();
    });

    it("o botão de olho mostra e oculta os nomes dos outros jogadores", async () => {
      const user = userEvent.setup();
      await aberta(comNomes());
      const botao = screen.getByRole("button", { name: "Mostrar nomes" });

      await user.click(botao);

      expect(botao).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByText("Mago Teste 1")).toBeInTheDocument();
      expect(screen.getAllByText("(Reino Teste)")).toHaveLength(10);
      expect(screen.queryByText("Top 1")).not.toBeInTheDocument();

      await user.click(botao);

      expect(botao).toHaveAttribute("aria-pressed", "false");
      expect(screen.queryByText(/Mago Teste/)).not.toBeInTheDocument();
      expect(screen.getByText("Top 1")).toBeInTheDocument();
    });

    it("lembra a escolha de mostrar nomes na próxima análise aberta", async () => {
      const user = userEvent.setup();
      const primeira = await aberta(comNomes());
      await user.click(screen.getByRole("button", { name: "Mostrar nomes" }));
      primeira.unmount();

      await aberta(comNomes());

      expect(screen.getByRole("button", { name: "Mostrar nomes" })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      expect(screen.getByText("Mago Teste 1")).toBeInTheDocument();
    });

    it("se o navegador lembrava 'mostrar' mas a análise não tem nomes, continua oculto", async () => {
      window.localStorage.setItem("logcoach.showNames", "true");
      await aberta();

      expect(screen.getByText("Top 1")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Mostrar nomes" })).toHaveAttribute(
        "aria-pressed",
        "false",
      );
    });
  });

  describe("abas", () => {
    it("começa no Resumo, com as três abas disponíveis", async () => {
      await aberta();

      expect(screen.getAllByRole("tab").map((item) => item.textContent)).toEqual([
        "Resumo",
        "Linha do tempo",
        "Todas as regras",
      ]);
      expect(aba("Resumo")).toHaveAttribute("aria-selected", "true");
      expect(screen.getByRole("tabpanel")).toHaveAccessibleName("Resumo");
    });

    it("linha do tempo: uma linha por habilidade, com seus usos e os dos melhores", async () => {
      const user = userEvent.setup();
      await aberta();

      await user.click(aba("Linha do tempo"));

      expect(aba("Linha do tempo")).toHaveAttribute("aria-selected", "true");
      expect(screen.getByRole("tabpanel")).toHaveAccessibleName("Linha do tempo");
      expect(screen.queryByText("Erros do maior para o menor impacto")).not.toBeInTheDocument();
      expect(screen.getAllByRole("img")).toHaveLength(5);
      expect(
        screen.getByRole("img", {
          name: "Surto Arcano. Você: 0:03, 1:39, 3:11, 4:49, 6:24. Melhores: 0:03, 1:35, 3:08, 4:41.",
        }),
      ).toBeInTheDocument();
      expect(screen.getByText("Intermissão", { selector: ".timeline-phase-name" })).toBeVisible();
      expect(screen.getByText("Potencial da Luz (poção)")).toBeInTheDocument();
    });

    it("todas as regras: tabela com a situação, a referência dos tops e o custo", async () => {
      const user = userEvent.setup();
      await aberta();

      await user.click(aba("Todas as regras"));

      const cabecalhos = within(tabelaComColuna("Regra"))
        .getAllByRole("columnheader")
        .map((c) => c.textContent);
      expect(cabecalhos).toEqual(["Regra", "Você", "Melhores", "Referência", "Situação"]);

      const linha = screen
        .getByRole("rowheader", { name: /Entradas na Alma Arcana com menos de 12 de Salvo/ })
        .closest("tr");
      expect(linha).toHaveTextContent("2 de 5 (0, 20, 1, 18, 22)");
      expect(linha).toHaveTextContent("9 de 43");
      expect(linha).toHaveTextContent("✕ Erro");
      expect(linha).toHaveTextContent("custou ~2,7% do dano");
      expect(linha).toHaveTextContent("Ideal: 20 ou mais (você: 2 de 5).");
      expect(within(linha).getByText("2 detalhes")).toBeInTheDocument();
      expect(within(linha).getByText("Entrada aos 3:28 com 1 de Salvo")).toBeInTheDocument();
    });

    it("regra com um detalhe só usa o singular; regra ok não mostra custo", async () => {
      const user = userEvent.setup();
      await aberta();
      await user.click(aba("Todas as regras"));

      const combo = screen
        .getByRole("rowheader", { name: /Surto Arcano → Toque dos Magos em até 3,5 s/ })
        .closest("tr");
      expect(within(combo).getByText("1 detalhe")).toBeInTheDocument();
      const usos = screen.getByRole("rowheader", { name: /Usos de Toque dos Magos/ }).closest("tr");
      expect(usos).toHaveTextContent("✓ OK");
      expect(usos).not.toHaveTextContent("custou");
      expect(usos).toHaveTextContent("Possível = usar no CD desde o pull até o fim da luta.");
    });

    it("sem referência em nenhuma regra (análise antiga) a coluna some", async () => {
      const user = userEvent.setup();
      await aberta(
        variacao((a) => {
          a.result.rules.forEach((regra) => {
            regra.reference = null;
          });
        }),
      );
      await user.click(aba("Todas as regras"));

      expect(screen.queryByRole("columnheader", { name: "Referência" })).not.toBeInTheDocument();
    });

    it("tabelas por habilidade e por fase, você / tops", async () => {
      const user = userEvent.setup();
      await aberta();
      await user.click(aba("Todas as regras"));

      const fase1 = tabelaComColuna("Habilidade", "Fase 1");
      const linha = within(fase1).getByRole("row", { name: /Mísseis Arcanos/ });
      expect(linha).toHaveTextContent("16,2 / 16,4");
      expect(linha).toHaveTextContent("35,1 / 33,9");
      expect(tabelaComColuna("Habilidade", "Intermissão")).toBeInTheDocument();
    });

    it("dano por alvo, com o chefe destacado", async () => {
      const user = userEvent.setup();
      await aberta();
      await user.click(aba("Todas as regras"));

      expect(screen.getByRole("heading", { name: /Dano por alvo/ })).toBeInTheDocument();
      const alvos = tabelaComColuna("Alvo", "Fase 1");
      const chefe = within(alvos).getByRole("rowheader", { name: /Nek'zali, a Enrosca-almas/ });
      expect(chefe).toHaveTextContent("Chefe");
      expect(chefe.closest("tr")).toHaveTextContent("81,7 / 81,9");
      expect(
        within(alvos).getByRole("rowheader", { name: "Amani Indócil" }).closest("tr"),
      ).toHaveTextContent("16,8 / 15,7");
    });

    it("sem violações de acessibilidade em cada aba", async () => {
      const user = userEvent.setup();
      const { container } = await aberta();
      expect(await axeViolations(container)).toEqual([]);

      await user.click(aba("Linha do tempo"));
      expect(await axeViolations(container)).toEqual([]);

      await user.click(aba("Todas as regras"));
      expect(await axeViolations(container)).toEqual([]);
    });
  });

  describe("erros ao abrir", () => {
    it("análise que não existe: mostra a mensagem e o caminho de volta", async () => {
      renderResult(apiError(404, "analysis_not_found", "Não encontramos essa análise."), {
        id: "inexistente",
      });

      const aviso = await screen.findByRole("alert");
      expect(aviso).toHaveTextContent("Não deu para abrir essa análise");
      expect(aviso).toHaveTextContent("Não encontramos essa análise.");
      expect(screen.getByRole("link", { name: "← Fazer uma nova análise" })).toHaveAttribute(
        "href",
        "#/",
      );
    });

    it("sem login: sugere entrar e volta para a mesma análise depois", async () => {
      renderResult(apiError(404, "analysis_not_found", "Não encontramos essa análise."), {
        id: "abc/123",
      });

      const aviso = await screen.findByRole("alert");
      expect(aviso).toHaveTextContent("Se ela é da sua conta, entre para abrir.");
      expect(within(aviso).getByRole("link", { name: "Entrar" })).toHaveAttribute(
        "href",
        "#/entrar?modo=login&depois=%2Fanalise%2Fabc%2F123",
      );
    });

    it("com login não oferece 'Entrar' nem o texto de entrar", async () => {
      renderResult(apiError(404, "analysis_not_found", "Não encontramos essa análise."), {
        id: "outra",
        logado: true,
      });

      const aviso = await screen.findByRole("alert");
      expect(within(aviso).queryByRole("link", { name: "Entrar" })).not.toBeInTheDocument();
      expect(aviso).not.toHaveTextContent("entre para abrir");
    });

    it("erro nosso (500 sem código) e rede fora têm mensagem própria", async () => {
      const { unmount } = renderResult(
        { status: 500, body: "<html>erro</html>", html: true },
        { id: "x1" },
      );
      expect(await screen.findByRole("alert")).toHaveTextContent("Erro inesperado no LogCoach.");
      unmount();

      renderResult(new TypeError("Failed to fetch"), { id: "x2" });
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "O servidor do LogCoach não respondeu.",
      );
    });

    it("sem violações de acessibilidade na tela de erro", async () => {
      const { container } = renderResult(
        apiError(404, "analysis_not_found", "Não encontramos essa análise."),
      );
      await screen.findByRole("alert");
      expect(await axeViolations(container)).toEqual([]);
    });
  });
});
