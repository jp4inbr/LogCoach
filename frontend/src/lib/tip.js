// Posição da dica de um termo (Term.jsx): deslocamento para a esquerda, em px, para a dica não
// sair da tela perto da borda direita, no celular ou no PC.
const MARGIN = 12;
const TIP_MAX = 280;

export function tipShift(termLeft, viewportWidth) {
  const width = Math.min(TIP_MAX, viewportWidth * 0.8);
  const overflow = termLeft + width - (viewportWidth - MARGIN);
  if (overflow <= 0) return 0;
  // Desloca o necessário, mas sem passar da margem esquerda da tela.
  return -Math.min(overflow, Math.max(0, termLeft - MARGIN));
}
