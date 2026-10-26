import { useMemo, useState } from "react";
import { AuthContext } from "../lib/auth-context.js";
import { load, save } from "../lib/storage.js";

const KEY = "logcoach.session";

export default function AuthProvider({ children }) {
  const [session, setSession] = useState(() => load(KEY));

  const value = useMemo(
    () => ({
      token: session?.token ?? null,
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
    [session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
