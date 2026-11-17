import { useTheme } from "../lib/theme.js";
import Icon from "./Icon.jsx";

// Botão do cabeçalho que alterna entre tema claro e escuro. O nome diz a ação (o que vai
// acontecer ao clicar); o ícone é só enfeite para quem enxerga.
export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const label = theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro";
  return (
    <button
      type="button"
      className="theme-toggle"
      data-theme-state={theme}
      onClick={toggle}
      aria-label={label}
      title={label}
    >
      {/* Chave em pílula: o botão escuro fica à esquerda, o claro à direita. O ícone na bolinha
          mostra o tema que o clique ativa, como o nome do botão. */}
      <span className="theme-toggle-track">
        <span className="theme-toggle-knob">
          <Icon name={theme === "dark" ? "sun" : "moon"} />
        </span>
      </span>
    </button>
  );
}
