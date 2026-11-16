// Termo técnico com uma dica curta ao passar o mouse ou tocar (heurística "ajuda e documentação").
export default function Term({ children, tip, label }) {
  return (
    <span className="term" tabIndex={0} data-tip={tip} aria-label={`${label ?? children}: ${tip}`}>
      {children}
    </span>
  );
}
