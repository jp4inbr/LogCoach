import { passwordStrength } from "../lib/passwordStrength.js";

// Medidor de força da senha (cadastro). Só informa: a senha fraca continua aceita se tiver
// o mínimo de caracteres. Quatro segmentos + o nome do nível em texto (a cor não é a única pista).
export default function PasswordStrength({ id, password }) {
  const strength = passwordStrength(password);
  if (!strength) {
    return (
      <p id={id} className="field-hint">
        Mínimo de 8 caracteres.
      </p>
    );
  }
  return (
    <div id={id} className={`strength strength-${strength.level}`}>
      <div className="strength-bar" aria-hidden="true">
        {[0, 1, 2, 3].map((segment) => (
          <span key={segment} className={segment <= strength.level ? "on" : undefined} />
        ))}
      </div>
      <p className="field-hint" aria-live="polite">
        Força da senha: <strong className="strength-label">{strength.label}</strong>
        {strength.tip && <> · {strength.tip}</>}
      </p>
    </div>
  );
}
