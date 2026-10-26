import { useEffect, useState } from "react";
import { api } from "./api.js";

// Busca um GET da API. O componente que usa deve ser remontado (key) quando o caminho muda.
export function useRequest(path, token) {
  const [state, setState] = useState({ status: "loading", data: null, error: null });

  useEffect(() => {
    let active = true;
    api
      .get(path, token)
      .then((data) => active && setState({ status: "ok", data, error: null }))
      .catch((error) => active && setState({ status: "error", data: null, error }));
    return () => {
      active = false;
    };
  }, [path, token]);

  return state;
}
