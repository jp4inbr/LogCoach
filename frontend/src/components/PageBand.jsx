// Faixa-título das telas internas: o mesmo idioma do hero da tela inicial (fundo do hero,
// sobretítulo em caixa alta, título forte e 2ª linha atenuada), bem mais baixa. A ação da
// tela (voltar, nova análise) fica ao lado, à direita.
export default function PageBand({ eyebrow, title, sub, aside }) {
  return (
    <div className="page-band">
      <div className="page-band-text">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {sub && <p className="page-band-sub">{sub}</p>}
      </div>
      {aside && <div className="page-band-aside">{aside}</div>}
    </div>
  );
}
