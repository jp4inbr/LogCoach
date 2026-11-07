// Acessibilidade nos testes: roda o axe-core no container renderizado e devolve as violações.
// O jsdom não calcula estilos, então a checagem de contraste (color-contrast) fica de fora aqui:
// o contraste das paletas é testado nos tokens (theme-contrast.test.js) e no navegador (e2e/).
import axe from "axe-core";

export async function axeViolations(container) {
  const results = await axe.run(container, {
    rules: { "color-contrast": { enabled: false } },
  });
  return results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
}
