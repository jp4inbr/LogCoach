import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import PageBand from "./PageBand.jsx";

describe("PageBand (faixa-título das telas internas)", () => {
  it("tem sobretítulo, o h1 com o título, a 2ª linha atenuada e a ação ao lado", () => {
    const { container } = render(
      <PageBand
        eyebrow="Planos"
        title="Escolha como quer evoluir"
        sub="Uma linha de apoio"
        aside={<a href="#/">Voltar</a>}
      />,
    );

    const band = container.querySelector(".page-band");
    expect(band).not.toBeNull();
    expect(within(band).getByText("Planos")).toHaveClass("eyebrow");
    expect(within(band).getByRole("heading", { level: 1 })).toHaveAccessibleName(
      "Escolha como quer evoluir",
    );
    expect(within(band).getByText("Uma linha de apoio")).toHaveClass("page-band-sub");
    expect(within(band).getByRole("link", { name: "Voltar" })).toBeInTheDocument();
  });

  it("sem 2ª linha nem ação, mostra só sobretítulo e título", () => {
    const { container } = render(<PageBand eyebrow="Conta" title="Seu perfil" />);
    expect(container.querySelector(".page-band-sub")).toBeNull();
    expect(container.querySelector(".page-band-aside")).toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "Seu perfil" })).toBeInTheDocument();
  });

  it("não tem violações de acessibilidade", async () => {
    const { container } = render(<PageBand eyebrow="Conta" title="Seu perfil" sub="voce@x.com" />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
