import { formatNumber } from "../lib/format.js";
import Term from "./Term.jsx";

// Dano por alvo e por fase: % no chefe e em cada add, você × média dos tops. Bater em add não é
// erro (eles têm de morrer); o chefe vem destacado porque é onde o ideal é ficar o máximo.
export default function TargetsTable({ targets }) {
  if (!targets || targets.length === 0) return null;
  return (
    <>
      <h2>
        Dano por alvo{" "}
        <Term tip="Parte do seu dano em cada alvo, fase a fase, ao lado da média dos melhores. Bater nos adds não é erro: eles precisam morrer. O ideal é deixar o máximo possível no chefe.">
          (o que é?)
        </Term>
      </h2>
      {targets.map((table) => (
        <div className="table-wrap" key={table.phase}>
          <table className="abilities targets">
            <caption>{table.phase}</caption>
            <thead>
              <tr>
                <th scope="col">Alvo</th>
                <th scope="col">% do dano (você / tops)</th>
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => (
                <tr key={row.name} className={row.boss ? "target-boss" : undefined}>
                  <th scope="row">
                    {row.name}
                    {row.boss && <span className="badge badge-boss">Chefe</span>}
                  </th>
                  <td>
                    {formatNumber(row.player_pct)} / {formatNumber(row.top_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </>
  );
}
