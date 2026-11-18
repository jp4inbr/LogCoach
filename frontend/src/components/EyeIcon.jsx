// Olho aberto (exibindo) ou cortado (oculto). Usado no "Mostrar nomes" (RF25) e no "Mostrar
// senha": o mesmo ícone para a mesma ideia (heurística "consistência e padrões").
export default function EyeIcon({ open }) {
  return (
    <svg className="eye-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
      {!open && <line x1="3" y1="3" x2="21" y2="21" />}
    </svg>
  );
}
