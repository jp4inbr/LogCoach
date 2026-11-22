import Icon from "./Icon.jsx";

// Mesmo padrão de cor e texto para ok / atenção / erro em todas as telas (heurística "consistência").
const LABELS = { ok: "OK", atencao: "Atenção", erro: "Erro" };
const ICONS = { ok: "check", atencao: "alert", erro: "x" };

export default function StatusBadge({ status }) {
  return (
    <span className={`badge badge-${status}`}>
      <Icon name={ICONS[status]} /> {LABELS[status]}
    </span>
  );
}
