// Dados de apoio dos testes de componente: recortes do resultado real do modo exemplo
// (analysis.json), só com pseudônimos.
import analysis from "./analysis.json";

export const result = analysis.result;
export const comparison = result.comparison;
export const gap = result.gap;
export const timeline = result.timeline;
export const phases = result.phases;
export const targets = result.targets;
export const mistakes = result.mistakes;

// Os três primeiros tops com nomes reais fictícios, como a API devolveria quando os nomes
// estão disponíveis (nunca nomes de jogadores de verdade); os demais seguem sem nome.
export const comparisonWithNames = {
  ...comparison,
  players: comparison.players.map((player, index) => ({
    ...player,
    name: ["Aldrin", "Belisa", "Corvo"][index] ?? null,
    server: ["Azralon", "Nemesis", null][index] ?? null,
  })),
};
