import { render } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import icons from "../data/spell-icons.json";
import { plainSpellText } from "../lib/spellText.js";
import SpellIcon from "./SpellIcon.jsx";
import SpellText, { SpellName } from "./SpellText.jsx";

const TEXT =
  "Depois do {{spell:365350|Surto}} vem a {{spell:451038|Alma Arcana}}, sem {{spell:1|X}}.";

describe("SpellText", () => {
  it("põe o ícone do catálogo antes do nome, com alt vazio", () => {
    const { container } = render(<SpellText text={TEXT} />);
    const refs = container.querySelectorAll(".spell-ref");
    expect(refs).toHaveLength(2); // o ID 1 não tem ícone: texto puro
    const first = refs[0].querySelector(".spell-lead").firstElementChild;
    expect(first.tagName).toBe("IMG");
    expect(first.getAttribute("src")).toMatch(new RegExp(`/icons/${icons["365350"]}$`));
    expect(first).toHaveAttribute("alt", "");
    expect(first).toHaveAttribute("aria-hidden", "true");
    // O texto vem depois do ícone, no mesmo span.
    expect(refs[0].querySelector(".spell-lead").lastChild.textContent).toBe("Surto");
  });

  it("ID fora do catálogo mostra só o texto, sem img", () => {
    const { container } = render(<SpellText text="a {{spell:1|X}} b" />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector(".spell-ref")).toBeNull(); // texto puro, sem span
    expect(container.textContent).toBe("a X b");
  });

  it("SpellName sem ícone no catálogo é texto puro, sem span", () => {
    const { container } = render(
      <SpellName id={10060}>Infusão de Poder (de outro jogador)</SpellName>,
    );
    expect(container.querySelector("span")).toBeNull();
    expect(container.textContent).toBe("Infusão de Poder (de outro jogador)");
  });

  it("SpellName com ícone: só o ícone e a primeira palavra ficam sem quebra", () => {
    const { container } = render(<SpellName id={451038}>Alma Arcana (entrada)</SpellName>);
    const ref = container.querySelector(".spell-ref");
    expect(ref).toHaveAttribute("data-spell-id", "451038");
    const lead = ref.querySelector(".spell-lead");
    expect(lead.firstElementChild.tagName).toBe("IMG");
    expect(lead.textContent).toBe("Alma");
    expect(ref.textContent).toBe("Alma Arcana (entrada)");
  });

  it("o textContent é o texto exibido, sem marcação", () => {
    const { container } = render(<SpellText text={TEXT} />);
    expect(container.textContent).toBe(plainSpellText(TEXT));
  });

  it("texto nulo não renderiza nada", () => {
    const { container } = render(<SpellText text={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("SpellIcon", () => {
  it("tem tamanho fixo e carregamento preguiçoso", () => {
    const { container } = render(<SpellIcon id={365350} />);
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("width");
    expect(img).toHaveAttribute("height");
    expect(img).toHaveAttribute("loading", "lazy");
  });

  it("some se a imagem falhar ao carregar", () => {
    const { container } = render(<SpellIcon id={365350} />);
    fireEvent.error(container.querySelector("img"));
    expect(container.querySelector("img")).toBeNull();
  });

  it("não renderiza nada para ID desconhecido", () => {
    const { container } = render(<SpellIcon id={999999999} />);
    expect(container).toBeEmptyDOMElement();
  });
});
