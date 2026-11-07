import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { href, navigate, useRoute } from "./router.js";

function Probe() {
  const { path, parts, params } = useRoute();
  return (
    <div>
      <p data-testid="path">{path}</p>
      <p data-testid="parts">{JSON.stringify(parts)}</p>
      <p data-testid="params">{JSON.stringify(Object.fromEntries(params))}</p>
    </div>
  );
}

async function goTo(hash) {
  await act(async () => {
    window.location.hash = hash;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

describe("href", () => {
  it("monta o link de hash", () => {
    expect(href("/login")).toBe("#/login");
  });
});

describe("navigate", () => {
  it("troca o hash da página", () => {
    navigate("/planos");
    expect(window.location.hash).toBe("#/planos");
  });
});

describe("useRoute", () => {
  it("sem hash, a rota é a raiz", () => {
    render(<Probe />);
    expect(screen.getByTestId("path")).toHaveTextContent("/");
    expect(screen.getByTestId("parts")).toHaveTextContent("[]");
    expect(screen.getByTestId("params")).toHaveTextContent("{}");
  });

  it("separa o caminho em partes e lê a query", () => {
    window.location.hash = "#/resultado/12?report=XhrmBaYkGCAQjH2D&fight=34";
    render(<Probe />);
    expect(screen.getByTestId("path")).toHaveTextContent("/resultado/12");
    expect(screen.getByTestId("parts")).toHaveTextContent('["resultado","12"]');
    expect(screen.getByTestId("params")).toHaveTextContent(
      '{"report":"XhrmBaYkGCAQjH2D","fight":"34"}',
    );
  });

  it("reage à mudança de hash (botão voltar do navegador)", async () => {
    render(<Probe />);
    await goTo("#/perfil");
    expect(screen.getByTestId("path")).toHaveTextContent("/perfil");
    await goTo("#/planos?x=1");
    expect(screen.getByTestId("path")).toHaveTextContent("/planos");
    expect(screen.getByTestId("params")).toHaveTextContent('{"x":"1"}');
  });

  it("para de ouvir o hashchange ao desmontar", async () => {
    const { unmount } = render(<Probe />);
    unmount();
    await goTo("#/perfil");
    expect(window.location.hash).toBe("#/perfil");
  });
});
