import { createContext, useContext } from "react";

export const AuthContext = createContext(null);

// { token, email, login(token, email), logout() }
export function useAuth() {
  return useContext(AuthContext);
}
