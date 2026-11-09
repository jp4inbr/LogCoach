import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axeViolations } from "../test/axe.js";
import AutoRefreshNotice from "./AutoRefreshNotice.jsx";

const INTERVAL = 4 * 60_000;

function notice(props = {}) {
  return (
    <AutoRefreshNotice
      state="waiting"
      busy={false}
      lastDoneAt={Date.now()}
      intervalMs={INTERVAL}
      stopAfter={3}
      {...props}
    />
  );
}

beforeEach(() => vi.useFakeTimers({ now: new Date("2026-11-04T20:00:00Z") }));
afterEach(() => vi.useRealTimers());

describe("AutoRefreshNotice", () => {
  it("desligada: só deixa uma região viva vazia, escondida da tela", () => {
    const { container } = render(notice({ state: "off" }));
    expect(container.firstChild).toHaveClass("sr-only");
    expect(container.firstChild).not.toHaveClass("auto-refresh");
    expect(container).toHaveTextContent("");
    expect(container.querySelector("[aria-live='polite']")).toBeInTheDocument();
  });

  it("luta subindo: avisa que acompanha o log ao vivo", () => {
    render(notice({ state: "uploading" }));
    expect(
      screen.getByText("Acompanhando o log ao vivo", { selector: "strong" }).closest("span"),
    ).toHaveTextContent("Acompanhando o log ao vivo (luta subindo para o Warcraft Logs)");
  });

  it("esperando o próximo pull", () => {
    render(notice({ state: "waiting" }));
    expect(screen.getByText(/esperando o próximo pull/)).toBeInTheDocument();
  });

  it("parada: explica o motivo e quanto tempo isso representa", () => {
    const { container } = render(notice({ state: "stopped", stopAfter: 3, intervalMs: INTERVAL }));
    expect(container.firstChild).toHaveClass("auto-refresh", "auto-refresh-stopped");
    expect(container).toHaveTextContent(
      "Atualização automática parada: nada mudou nas últimas 3 atualizações (cerca de 12 min).",
    );
    expect(container).toHaveTextContent("“Atualizar lutas” confere de novo e volta a acompanhar.");
  });

  it("parada não mostra contagem regressiva nem ‘buscando agora’", () => {
    const { container } = render(notice({ state: "stopped", busy: true }));
    expect(container.querySelector(".auto-refresh-status")).toBeNull();
  });

  it("a frase de estado fica na região viva e a contagem fora dela", () => {
    const { container } = render(notice({ state: "waiting" }));
    const live = container.querySelector("[aria-live='polite']");
    expect(live).toHaveTextContent("esperando o próximo pull");
    expect(live).not.toHaveTextContent("próxima atualização");
    expect(container.querySelector(".auto-refresh-status")).toHaveTextContent(
      "próxima atualização em 4 min",
    );
  });

  it("busca em andamento: mostra ‘buscando agora…’ com o ponto decorativo", () => {
    const { container } = render(notice({ busy: true }));
    expect(container.querySelector(".auto-refresh-status")).toHaveTextContent("buscando agora…");
    expect(container.querySelector(".auto-refresh-dot")).toHaveAttribute("aria-hidden", "true");
    expect(container).not.toHaveTextContent("próxima atualização");
  });

  it("sem nenhuma busca concluída ainda (lastDoneAt nulo) não mostra contagem", () => {
    const { container } = render(notice({ lastDoneAt: null }));
    expect(container.querySelector(".auto-refresh-status").textContent).toBe(": ");
    expect(container).not.toHaveTextContent("próxima atualização");
  });

  it("a contagem arredonda os minutos para cima", () => {
    const { container } = render(notice({ lastDoneAt: Date.now() }));
    act(() => vi.advanceTimersByTime(61_000));
    // Faltam 179 s: 2,98 min viram 3.
    expect(container).toHaveTextContent("próxima atualização em 3 min");
  });

  it("menos de 1 min antes da próxima busca", () => {
    const { container } = render(notice({ lastDoneAt: Date.now() }));
    act(() => vi.advanceTimersByTime(INTERVAL - 30_000));
    expect(container).toHaveTextContent("próxima atualização em menos de 1 min");
    expect(container).toHaveTextContent("(ou clique em “Atualizar lutas”)");
  });

  it("a contagem anda sozinha com o relógio e termina em ‘atualizando em instantes…’", () => {
    const { container } = render(notice({ lastDoneAt: Date.now() }));
    expect(container).toHaveTextContent("próxima atualização em 4 min");

    act(() => vi.advanceTimersByTime(60_000));
    expect(container).toHaveTextContent("próxima atualização em 3 min");

    act(() => vi.advanceTimersByTime(2 * 60_000 + 30_000));
    expect(container).toHaveTextContent("menos de 1 min");

    act(() => vi.advanceTimersByTime(30_000));
    expect(container).toHaveTextContent("atualizando em instantes…");
    expect(container).not.toHaveTextContent("próxima atualização");
  });

  it("uma busca nova (lastDoneAt novo) reinicia a contagem", () => {
    const { container, rerender } = render(notice({ lastDoneAt: Date.now() }));
    act(() => vi.advanceTimersByTime(3 * 60_000));
    expect(container).toHaveTextContent("em 1 min");

    rerender(notice({ lastDoneAt: Date.now() }));
    expect(container).toHaveTextContent("em 4 min");
  });

  it("para o relógio ao desmontar", () => {
    const { unmount } = render(notice());
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each(["off", "uploading", "waiting", "stopped"])(
    "estado %s não tem violações de acessibilidade",
    async (state) => {
      // O axe usa timers internos: com os falsos ele não termina.
      vi.useRealTimers();
      const { container } = render(notice({ state, lastDoneAt: Date.now() }));
      expect(await axeViolations(container)).toEqual([]);
    },
  );
});
