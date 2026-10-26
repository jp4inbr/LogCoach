// Termo técnico com uma dica curta ao passar o mouse ou tocar (heurística "ajuda e documentação").
export default function Term({ children, tip }) {
  return (
    <span className="term" tabIndex={0} data-tip={tip} aria-label={`${children}: ${tip}`}>
      {children}
    </span>
  );
}
