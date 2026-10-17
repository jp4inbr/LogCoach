import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function App() {
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((response) => response.json())
      .then((data) => setStatus(data.status === "ok" ? "ok" : "error"))
      .catch(() => setStatus("error"));
  }, []);

  const messages = {
    loading: "Verificando o backend...",
    ok: "Backend respondeu: tudo certo.",
    error: "Backend não respondeu. Ele está rodando em http://localhost:8000?",
  };

  return (
    <main>
      <h1>LogCoach</h1>
      <p>{messages[status]}</p>
    </main>
  );
}

export default App;
