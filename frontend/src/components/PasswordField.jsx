import { useState } from "react";
import EyeIcon from "./EyeIcon.jsx";

// Campo de senha com "Mostrar senha" (o olho). O rótulo do botão não muda: ligado/desligado
// vem do aria-pressed e do ícone, como no "Mostrar nomes" do resultado (padrão WAI-ARIA).
// children: dica, erro ou medidor, abaixo do campo.
export default function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete,
  invalid = false,
  describedBy,
  toggleLabel = `Mostrar ${label.toLowerCase()}`,
  children,
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="password-row">
        <input
          id={id}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck="false"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={invalid ? "true" : "false"}
          aria-describedby={describedBy}
        />
        <button
          type="button"
          className="button small ghost eye-toggle password-toggle"
          aria-pressed={visible}
          aria-controls={id}
          aria-label={toggleLabel}
          onClick={() => setVisible((current) => !current)}
        >
          <EyeIcon open={visible} />
        </button>
      </div>
      {children}
    </div>
  );
}
