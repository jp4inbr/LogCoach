import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axeViolations } from "../test/axe.js";
import Splash, { SPLASH_FADE_MS, SPLASH_MS } from "./Splash.jsx";

/** matchMedia falso que só responde à preferência de menos movimento. */
function stubReducedMotion(reduce) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query) => ({
      matches: query === "(prefers-reduced-motion: reduce)" && reduce,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("Splash", () => {
  it("mostra a abertura em tela cheia e some depois da animação", () => {
    vi.useFakeTimers();
    stubReducedMotion(false);
    render(<Splash />);

    const splash = screen.getByTestId("splash");
    expect(splash).toHaveClass("splash");
    expect(splash).not.toHaveClass("splash-leaving");
    expect(splash.querySelector(".splash-light")).toBeInTheDocument();
    expect(splash.querySelector(".splash-line")).toHaveAttribute("pathLength", "100");
    expect(splash.querySelector(".splash-dot")).toBeInTheDocument();
    expect(splash).toHaveTextContent("LOGCOACH");

    act(() => vi.advanceTimersByTime(SPLASH_MS));
    expect(screen.getByTestId("splash")).toHaveClass("splash-leaving");

    act(() => vi.advanceTimersByTime(SPLASH_FADE_MS));
    expect(screen.queryByTestId("splash")).not.toBeInTheDocument();
  });

  it("exibe o texto LOGCOACH escondido dos leitores de tela", () => {
    stubReducedMotion(false);
    render(<Splash />);
    const splash = screen.getByTestId("splash");
    expect(splash).toHaveAttribute("aria-hidden", "true");
    expect(splash).toHaveTextContent("LOGCOACH");
  });

  it("não aparece para quem pede menos movimento", () => {
    stubReducedMotion(true);
    render(<Splash />);
    expect(screen.queryByTestId("splash")).not.toBeInTheDocument();
  });

  it("sem matchMedia, toca normalmente", () => {
    vi.stubGlobal("matchMedia", undefined);
    render(<Splash />);
    expect(screen.getByTestId("splash")).toBeInTheDocument();
  });

  it("desmontar no meio não deixa timer pendente", () => {
    vi.useFakeTimers();
    stubReducedMotion(false);
    const { unmount } = render(<Splash />);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("não tem violações do axe", async () => {
    stubReducedMotion(false);
    const { container } = render(<Splash />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
