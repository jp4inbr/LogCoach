// Mesmo padrão de cor e texto para ok / atenção / erro em todas as telas (heurística "consistência").
const LABELS = { ok: "OK", atencao: "Atenção", erro: "Erro" };
const ICONS = { ok: "✓", atencao: "!", erro: "✕" };

export default function StatusBadge({ status }) {
  return (
    <span className={`badge badge-${status}`}>
      <span aria-hidden="true">{ICONS[status]}</span> {LABELS[status]}
    </span>
  );
}
