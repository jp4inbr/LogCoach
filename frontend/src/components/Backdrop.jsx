import { useEffect, useState } from "react";

// Cenário de fundo de todas as telas: Silvermoon de dia no tema claro e Suramar à noite no
// escuro, a mesma composição nas duas horas. Fixo na viewport, atrás de todo o conteúdo e só
// enfeite (aria-hidden, sem eventos de ponteiro).
//
// mode="pleno" (início e login): a cidade aparece, com um véu atrás do texto.
// mode="fundo" (demais telas): a cidade desfocada sob um véu forte, só a sensação de lugar.
//
// As duas imagens começam com loading="lazy": a do tema inativo está em display:none e o
// navegador não a baixa. Depois que a página carrega e fica ociosa, as duas viram "eager" e a
// outra é baixada em segundo plano, para a troca de tema não mostrar o fundo vazio.
const BASE = `${import.meta.env.BASE_URL}cenario/`;

const CITIES = [
  { name: "silvermoon", className: "backdrop-day" },
  { name: "suramar", className: "backdrop-night" },
];

export default function Backdrop({ mode }) {
  const warm = useWarmUp();
  return (
    <div className="backdrop" data-testid="cenario" data-cenario={mode} aria-hidden="true">
      {CITIES.map(({ name, className }) => (
        <picture key={name} className={`backdrop-city ${className}`}>
          <source
            media="(max-width: 700px) and (orientation: portrait)"
            srcSet={`${BASE}${name}-celular.webp`}
          />
          <img
            src={`${BASE}${name}-2400.webp`}
            srcSet={`${BASE}${name}-1440.webp 1440w, ${BASE}${name}-2400.webp 2400w`}
            sizes="100vw"
            alt=""
            loading={warm ? "eager" : "lazy"}
            decoding="async"
          />
        </picture>
      ))}
      <div className="backdrop-veil" />
    </div>
  );
}

/** true depois que a página carregou e o navegador ficou ocioso. */
function useWarmUp() {
  const [warm, setWarm] = useState(false);
  useEffect(() => {
    let idle;
    const schedule = () => {
      idle =
        "requestIdleCallback" in window
          ? window.requestIdleCallback(() => setWarm(true), { timeout: 4000 })
          : window.setTimeout(() => setWarm(true), 1500);
    };
    if (document.readyState === "complete") schedule();
    else window.addEventListener("load", schedule, { once: true });
    return () => {
      window.removeEventListener("load", schedule);
      if ("cancelIdleCallback" in window) window.cancelIdleCallback(idle);
      window.clearTimeout(idle);
    };
  }, []);
  return warm;
}
