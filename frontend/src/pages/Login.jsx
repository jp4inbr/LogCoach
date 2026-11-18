import { useState } from "react";
import PasswordField from "../components/PasswordField.jsx";
import PasswordStrength from "../components/PasswordStrength.jsx";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth-context.js";
import { MIN_PASSWORD } from "../lib/passwordStrength.js";
import { href, navigate } from "../lib/router.js";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Login e cadastro (RF02). Os erros aparecem no próprio campo, antes de enviar (item 8.2).
// Os campos de senha têm "Mostrar senha"; no cadastro, a senha é digitada duas vezes e um
// medidor mostra a força dela (só informa: o mínimo de 8 caracteres é a única exigência).
export default function Login({ mode, next }) {
  const { login } = useAuth();
  const isRegister = mode === "cadastro";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);
  const [serverError, setServerError] = useState(null);
  const [sending, setSending] = useState(false);

  const emailError = !EMAIL.test(email.trim())
    ? "Digite um e-mail válido, como voce@exemplo.com."
    : null;
  const passwordError = isRegister
    ? password.length < MIN_PASSWORD
      ? `A senha precisa ter pelo menos ${MIN_PASSWORD} caracteres.`
      : null
    : password
      ? null
      : "Digite sua senha.";
  const confirmError =
    isRegister && confirm !== password
      ? confirm
        ? "As senhas não são iguais."
        : "Digite a senha de novo para confirmar."
      : null;

  async function submit(event) {
    event.preventDefault();
    setTouched(true);
    setServerError(null);
    if (emailError || passwordError || confirmError) return;

    setSending(true);
    try {
      const body = { email: email.trim(), password };
      const { access_token: token } = await api.post(
        isRegister ? "/auth/register" : "/auth/login",
        body,
      );
      login(token, body.email.toLowerCase());
      navigate(next || "/perfil");
    } catch (error) {
      setServerError(error.message);
      setSending(false);
    }
  }

  const nextQuery = next ? `&depois=${encodeURIComponent(next)}` : "";

  return (
    <div className="auth">
      <div className="card auth-card">
        <div className="tabs" role="tablist" aria-label="Entrar ou criar conta">
          <a
            role="tab"
            aria-selected={!isRegister}
            className={`tab ${!isRegister ? "tab-active" : ""}`}
            href={href(`/entrar?modo=login${nextQuery}`)}
          >
            Entrar
          </a>
          <a
            role="tab"
            aria-selected={isRegister}
            className={`tab ${isRegister ? "tab-active" : ""}`}
            href={href(`/entrar?modo=cadastro${nextQuery}`)}
          >
            Criar conta
          </a>
        </div>

        <h1>{isRegister ? "Crie sua conta grátis" : "Entre na sua conta"}</h1>
        {isRegister && (
          <p className="muted">
            Com conta você guarda o histórico e faz até 5 análises por mês. Só pedimos e-mail e
            senha.
          </p>
        )}

        <form onSubmit={submit} noValidate className="form">
          <div className="field">
            <label htmlFor="email">E-mail</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={touched && emailError ? "true" : "false"}
            />
            {touched && emailError && <p className="field-error">{emailError}</p>}
          </div>

          <PasswordField
            id="password"
            label="Senha"
            value={password}
            onChange={setPassword}
            autoComplete={isRegister ? "new-password" : "current-password"}
            invalid={touched && Boolean(passwordError)}
            describedBy={isRegister ? "password-help" : undefined}
          >
            {touched && passwordError ? (
              <p className="field-error">{passwordError}</p>
            ) : (
              isRegister && <PasswordStrength id="password-help" password={password} />
            )}
          </PasswordField>

          {isRegister && (
            <PasswordField
              id="password-confirm"
              label="Confirmar senha"
              toggleLabel="Mostrar a confirmação da senha"
              value={confirm}
              onChange={setConfirm}
              autoComplete="new-password"
              invalid={touched && Boolean(confirmError)}
            >
              {touched && confirmError && <p className="field-error">{confirmError}</p>}
            </PasswordField>
          )}

          {serverError && (
            <p className="field-error" role="alert">
              {serverError}
            </p>
          )}

          <button type="submit" className="button primary block" disabled={sending}>
            {sending ? "Enviando…" : isRegister ? "Criar conta" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
