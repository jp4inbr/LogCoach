import { useTheme } from "../lib/theme.js";

// Botão do cabeçalho que alterna entre tema claro e escuro. O nome diz a ação (o que vai
// acontecer ao clicar); o ícone é só enfeite para quem enxerga.
export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const label = theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro";
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={label}
      title={label}
    >
      <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
    </button>
  );
}
