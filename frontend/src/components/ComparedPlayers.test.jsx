import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import { comparison, comparisonWithNames } from "../test/fixtures/components.js";
import ComparedPlayers from "./ComparedPlayers.jsx";

const eye = () => screen.getByRole("button", { name: "Mostrar nomes" });

describe("ComparedPlayers", () => {
  it.each([[{ ...comparison, players: [] }], [{ ...comparison, players: undefined }]])(
    "não mostra nada sem jogadores",
    (value) => {
      const { container } = render(<ComparedPlayers comparison={value} />);
      expect(container).toBeEmptyDOMElement();
    },
  );

  it("resume quem foi comparado", () => {
    render(<ComparedPlayers comparison={comparison} />);
    expect(screen.getByText("Com quem você foi comparado")).toBeInTheDocument();
    expect(screen.getByText("Top 10 do bracket 326–328 · 10 jogadores")).toBeInTheDocument();
  });

  it("usa o singular com um só jogador", () => {
    render(<ComparedPlayers comparison={{ ...comparison, players: [comparison.players[0]] }} />);
    expect(screen.getByText(/· 1 jogador$/)).toBeInTheDocument();
  });

  it("lista posição, pseudônimo, item level e DPS de cada top", () => {
    render(<ComparedPlayers comparison={comparison} />);
    const table = screen.getByRole("table", {
      name: "Top 10 do bracket 326–328: posição, jogador, item level e DPS",
    });
    expect(within(table).getAllByRole("row")).toHaveLength(11);
    const first = within(table).getByRole("row", { name: /^1º/ });
    expect(
      within(first)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["1º", "328", "279 mil"]);
    expect(within(table).getByRole("rowheader", { name: "Top 10" })).toBeInTheDocument();
  });

  it("sem nomes reais (modo exemplo): botão desabilitado, com o motivo escrito", () => {
    render(<ComparedPlayers comparison={comparison} />);
    expect(eye()).toBeDisabled();
    expect(eye()).toHaveAttribute("aria-pressed", "false");
    expect(eye()).toHaveAccessibleDescription("Nomes reais indisponíveis nos dados de exemplo.");
    expect(eye()).toHaveAttribute("title", "Nomes reais indisponíveis nos dados de exemplo");
  });

  it("sem nomes reais, a escolha guardada de mostrar não faz o botão parecer ligado", () => {
    window.localStorage.setItem("logcoach.showNames", "true");
    render(<ComparedPlayers comparison={comparison} />);
    expect(eye()).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("rowheader", { name: "Top 1" })).toBeInTheDocument();
  });

  it("com nomes disponíveis, eles ficam ocultos por padrão (RF25)", () => {
    render(<ComparedPlayers comparison={comparisonWithNames} />);
    expect(eye()).toBeEnabled();
    expect(eye()).toHaveAttribute("aria-pressed", "false");
    expect(eye()).toHaveAccessibleDescription(
      "Os nomes dos outros jogadores ficam ocultos por padrão. Você sempre aparece com o seu.",
    );
    expect(eye()).not.toHaveAttribute("title");
    expect(screen.queryByText(/Aldrin/)).not.toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "Top 1" })).toBeInTheDocument();
  });

  it("o botão de olho mostra os nomes e o servidor, e esconde de novo no segundo clique", async () => {
    render(<ComparedPlayers comparison={comparisonWithNames} />);
    await userEvent.click(eye());

    expect(eye()).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("rowheader", { name: /^Aldrin\s*\(Azralon\)$/ })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: /^Belisa\s*\(Nemesis\)$/ })).toBeInTheDocument();
    // Sem servidor, sem parênteses vazios.
    expect(screen.getByRole("rowheader", { name: "Corvo" })).toBeInTheDocument();
    expect(screen.queryByRole("rowheader", { name: "Top 1" })).not.toBeInTheDocument();

    await userEvent.click(eye());
    expect(eye()).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByText(/Aldrin/)).not.toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "Top 1" })).toBeInTheDocument();
  });

  it("o olho alterna também pelo teclado", async () => {
    render(<ComparedPlayers comparison={comparisonWithNames} />);
    eye().focus();
    await userEvent.keyboard("{Enter}");
    expect(eye()).toHaveAttribute("aria-pressed", "true");
    await userEvent.keyboard(" ");
    expect(eye()).toHaveAttribute("aria-pressed", "false");
  });

  it("guarda a escolha no navegador e a recupera na próxima análise", async () => {
    const { unmount } = render(<ComparedPlayers comparison={comparisonWithNames} />);
    await userEvent.click(eye());
    expect(JSON.parse(window.localStorage.getItem("logcoach.showNames"))).toBe(true);
    unmount();

    render(<ComparedPlayers comparison={comparisonWithNames} />);
    expect(eye()).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("rowheader", { name: /^Aldrin\s*\(Azralon\)$/ })).toBeInTheDocument();
  });

  it("um top sem nome real continua com o pseudônimo mesmo com os nomes à mostra", async () => {
    render(<ComparedPlayers comparison={comparisonWithNames} />);
    await userEvent.click(eye());
    expect(screen.getByRole("rowheader", { name: "Top 4" })).toBeInTheDocument();
  });

  it("item level ausente aparece como traço", () => {
    const players = [{ ...comparison.players[0], item_level: null }];
    render(<ComparedPlayers comparison={{ ...comparison, players }} />);
    expect(screen.getAllByRole("cell")[1]).toHaveTextContent("—");
  });

  it("não tem violações de acessibilidade (nomes ocultos e à mostra)", async () => {
    const { container } = render(<ComparedPlayers comparison={comparisonWithNames} />);
    expect(await axeViolations(container)).toEqual([]);
    await userEvent.click(eye());
    expect(await axeViolations(container)).toEqual([]);
  });

  it("não tem violações de acessibilidade no modo exemplo", async () => {
    const { container } = render(<ComparedPlayers comparison={comparison} />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
