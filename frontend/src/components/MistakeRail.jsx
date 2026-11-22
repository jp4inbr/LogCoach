import { useEffect, useState } from "react";

// Trilho numerado dos erros (aba Resumo): um link por erro, na ordem de custo, com o número na
// cor da situação. Em tela larga fica fixo à esquerda; abaixo de 1100 px vira uma faixa no topo
// da lista e rola junto (CSS). O erro que está no meio da tela fica marcado (aria-current)
// enquanto a pessoa rola; sem IntersectionObserver, nenhum fica marcado.
//
// items: [{ id, rank, title, severity }], title em texto puro (sem marcação de magia).
export default function MistakeRail({ items }) {
  const [current, setCurrent] = useState(null);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return undefined;
    const targets = items.map((item) => document.getElementById(item.id)).filter(Boolean);
    if (targets.length === 0) return undefined;
    // Faixa fina no meio da tela: o cartão que cruza a faixa é o que está sendo lido.
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting);
        if (visible.length > 0) setCurrent(visible[visible.length - 1].target.id);
      },
      { rootMargin: "-45% 0px -50% 0px" },
    );
    targets.forEach((target) => observer.observe(target));
    return () => observer.disconnect();
  }, [items]);

  function go(event, id) {
    const target = document.getElementById(id);
    if (!target) return;
    // O app usa o hash para as rotas (#/analise/...): o link não pode trocar o hash.
    event.preventDefault();
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    target.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    target.focus({ preventScroll: true });
    setCurrent(id);
  }

  return (
    <nav className="rail" aria-label="Erros por custo">
      <ol>
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              className={`rail-link rail-${item.severity}`}
              aria-label={`${item.rank}. ${item.title}`}
              aria-current={current === item.id ? "true" : undefined}
              onClick={(event) => go(event, item.id)}
            >
              {item.rank}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
