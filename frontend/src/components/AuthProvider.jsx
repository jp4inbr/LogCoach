import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api.js";
import { AuthContext } from "../lib/auth-context.js";
import { load, save } from "../lib/storage.js";

const KEY = "logcoach.session";

export default function AuthProvider({ children }) {
  const [session, setSession] = useState(() => load(KEY));
  const token = session?.token ?? null;

  // Sessão salva de uma visita antiga pode ter vencido. As rotas públicas aceitam token vencido
  // como "sem login", então confere aqui uma vez e sai da conta, em vez de o site parecer logado
  // e as análises deixarem de ir para o histórico sem aviso.
  useEffect(() => {
    if (!token) return;
    let active = true;
    api.get("/me", token).catch((error) => {
      if (active && error.code === "invalid_token") {
        save(KEY, null);
        setSession(null);
      }
    });
    return () => {
      active = false;
    };
  }, [token]);

  const value = useMemo(
    () => ({
      token,
      email: session?.email ?? null,
      login(token, email) {
        const next = { token, email };
        save(KEY, next);
        setSession(next);
      },
      logout() {
        save(KEY, null);
        setSession(null);
      },
    }),
    [session, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
