import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axeViolations } from "../test/axe.js";
import MistakeRail from "./MistakeRail.jsx";

const ITEMS = [
  { id: "erro-1", rank: 1, title: "Entrada na Alma Arcana com pouca Saraivada", severity: "erro" },
  { id: "erro-2", rank: 2, title: "Impactos Arcanos demais dentro do Surto", severity: "atencao" },
  { id: "erro-3", rank: 3, title: "Tempo ativo abaixo dos tops", severity: "atencao" },
];

// O trilho e os cartões que ele aponta (só o id e o foco importam aqui).
function renderWithCards(items = ITEMS) {
  const scrolls = [];
  const view = render(
    <>
      <MistakeRail items={items} />
      {items.map((item) => (
        <article key={item.id} id={item.id} tabIndex={-1}>
          {item.title}
        </article>
      ))}
    </>,
  );
  for (const item of items) {
    document.getElementById(item.id).scrollIntoView = vi.fn((options) =>
      scrolls.push([item.id, options]),
    );
  }
  return { ...view, scrolls };
}

// IntersectionObserver falso: guarda o callback para o teste dizer qual cartão cruzou a faixa.
function stubObserver() {
  const observers = [];
  class FakeObserver {
    constructor(callback, options) {
      this.callback = callback;
      this.options = options;
      this.targets = [];
      this.disconnect = vi.fn();
      observers.push(this);
    }
    observe(target) {
      this.targets.push(target);
    }
  }
  vi.stubGlobal("IntersectionObserver", FakeObserver);
  return observers;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MistakeRail", () => {
  it("é uma navegação 'Erros por custo' com um link por erro, na ordem de custo", () => {
    renderWithCards();
    const nav = screen.getByRole("navigation", { name: "Erros por custo" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual(["1", "2", "3"]);
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "#erro-1",
      "#erro-2",
      "#erro-3",
    ]);
  });

  it("o nome acessível de cada link traz o número e o título do erro", () => {
    renderWithCards();
    expect(
      screen.getByRole("link", { name: "1. Entrada na Alma Arcana com pouca Saraivada" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "3. Tempo ativo abaixo dos tops" }),
    ).toBeInTheDocument();
  });

  it("a cor da situação vem da classe de cada link", () => {
    renderWithCards();
    const [first, second] = screen.getAllByRole("link");
    expect(first).toHaveClass("rail-link", "rail-erro");
    expect(second).toHaveClass("rail-link", "rail-atencao");
  });

  it("clicar rola até o cartão, dá foco a ele, marca o link e não troca a rota (hash)", async () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: false })),
    );
    const user = userEvent.setup();
    window.location.hash = "#/analise/abc";
    const { scrolls } = renderWithCards();

    const link = screen.getByRole("link", { name: /^2\./ });
    await user.click(link);

    expect(scrolls).toEqual([["erro-2", { behavior: "smooth", block: "start" }]]);
    expect(document.getElementById("erro-2")).toHaveFocus();
    expect(link).toHaveAttribute("aria-current", "true");
    expect(window.location.hash).toBe("#/analise/abc");
  });

  it("com prefers-reduced-motion a rolagem é instantânea", async () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query) => ({ matches: query === "(prefers-reduced-motion: reduce)" })),
    );
    const user = userEvent.setup();
    const { scrolls } = renderWithCards();
    await user.click(screen.getByRole("link", { name: /^3\./ }));
    expect(scrolls).toEqual([["erro-3", { behavior: "auto", block: "start" }]]);
  });

  it("sem IntersectionObserver nenhum link vem marcado", () => {
    vi.stubGlobal("IntersectionObserver", undefined);
    renderWithCards();
    for (const link of screen.getAllByRole("link")) {
      expect(link).not.toHaveAttribute("aria-current");
    }
  });

  it("marca o erro que cruza o meio da tela enquanto a pessoa rola", () => {
    const observers = stubObserver();
    const { unmount } = renderWithCards();
    const [observer] = observers;
    expect(observer.targets.map((target) => target.id)).toEqual(["erro-1", "erro-2", "erro-3"]);
    expect(observer.options.rootMargin).toBe("-45% 0px -50% 0px");

    act(() =>
      observer.callback([
        { isIntersecting: true, target: document.getElementById("erro-3") },
        { isIntersecting: false, target: document.getElementById("erro-1") },
      ]),
    );
    expect(screen.getByRole("link", { name: /^3\./ })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("link", { name: /^1\./ })).not.toHaveAttribute("aria-current");

    unmount();
    expect(observer.disconnect).toHaveBeenCalled();
  });

  it("não tem violações do axe", async () => {
    vi.stubGlobal("IntersectionObserver", undefined);
    const { container } = renderWithCards();
    expect(await axeViolations(container)).toEqual([]);
  });
});
