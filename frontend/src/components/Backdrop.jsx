// Cenário de fundo de todas as telas: o mesmo da tela inicial (fundo do hero e a marca
// LogCoach gravada numa placa em perspectiva, com luz e rebites). Fixo na viewport, atrás de
// todo o conteúdo e só enfeite (aria-hidden, sem eventos de ponteiro). Um só no DOM: a tela
// inicial o põe dentro do hero; nas outras rotas, o App.
export default function Backdrop() {
  return (
    <div className="backdrop hero-art" data-testid="cenario" aria-hidden="true">
      <div className="hero-slab">
        <div className="hero-slab-top">
          <span className="hero-word">LogCoach</span>
          <span className="hero-sheen" />
        </div>
        <div className="hero-slab-front">
          <span className="hero-rivet" />
          <span className="hero-rivet" />
        </div>
      </div>
      <div className="hero-veil" />
    </div>
  );
}
