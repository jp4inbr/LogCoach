// matchMedia falso para os testes de tema (o jsdom não tem). Devolve o controle para mudar o
// tema do sistema com a página aberta. Quem usa deve chamar vi.unstubAllGlobals() ao final.
import { vi } from "vitest";

export function stubSystemTheme(initial = "dark") {
  let current = initial;
  const listeners = new Set();
  const media = {
    get matches() {
      return current === "light";
    },
    media: "(prefers-color-scheme: light)",
    addEventListener: (type, fn) => type === "change" && listeners.add(fn),
    removeEventListener: (type, fn) => type === "change" && listeners.delete(fn),
  };
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => media),
  );
  return {
    listenerCount: () => listeners.size,
    set(next) {
      current = next;
      listeners.forEach((fn) => fn({ matches: next === "light" }));
    },
  };
}
