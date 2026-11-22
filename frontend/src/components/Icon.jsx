// Ícones da interface, desenhados num traço só (grade de 24, traço de 2, pontas redondas) no
// lugar de símbolos de texto (←, ✓, ✕, ☀…). Decorativos por padrão: o texto ao lado ou o
// aria-label do controle é que dá o nome. A cor vem do texto (currentColor).
const PATHS = {
  "arrow-left": (
    <>
      <path d="M19 12H5" />
      <path d="m11 6-6 6 6 6" />
    </>
  ),
  check: <path d="m5 12.5 4.5 4.5L19 7" />,
  x: (
    <>
      <path d="M6.5 6.5 17.5 17.5" />
      <path d="M17.5 6.5 6.5 17.5" />
    </>
  ),
  // Exclamação: haste e ponto, a mesma leitura do "!" do selo de atenção.
  alert: (
    <>
      <path d="M12 5v9" />
      <path d="M12 19h.01" />
    </>
  ),
  "chevron-right": <path d="m9 6 6 6-6 6" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
    </>
  ),
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />,
  eye: (
    <>
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  "eye-off": (
    <>
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
      <path d="M3 3l18 18" />
    </>
  ),
  // Balão de conversa: o coach.
  message: (
    <path d="M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-7l-4.5 3.5V16H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z" />
  ),
};

export default function Icon({ name, size = "1em", className, label }) {
  const paths = PATHS[name];
  if (!paths) throw new Error(`Ícone desconhecido: ${name}`);
  return (
    <svg
      className={className ? `icon ${className}` : "icon"}
      data-icon={name}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": "true" })}
    >
      {paths}
    </svg>
  );
}
