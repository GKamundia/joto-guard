import { count, measure, number } from "../format";

const VERDICT_STYLE = {
  "non-standard": "bad",
  "does not match Stull": "bad",
  "matches Stull": "good",
  "within tolerance": "good",
  pending: "quiet",
  "report only": "quiet",
  "no usable rows": "quiet",
};

export default function Audits({ audits, thermometers }) {
  const signed = new Map(
    audits
      .filter((row) => row.metric === "mean_signed_diff_c")
      .map((row) => [row.variable, row.value]),
  );

  return (
    <section className="card">
      <h2>The station's own calculated columns</h2>
      <p className="lead">
        The station reports a wet bulb, a heat index and a WBGT that it works out itself. These
        checks compare them with the published formulas.
      </p>

      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Check</th>
              <th>Column</th>
              <th>Measure</th>
              <th className="number">Value</th>
              <th className="number">Rows</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {audits.map((row, index) => (
              <tr key={`${row.audit_id}-${row.variable}-${row.metric}-${index}`}>
                <td>{row.audit_id}</td>
                <td>{row.variable}</td>
                <td title={row.note ?? ""}>{row.metric?.replace(/_/g, " ")}</td>
                <td className="number">{measure(row.value)}</td>
                <td className="number">{count(row.n_rows)}</td>
                <td>
                  <span className={`pill ${VERDICT_STYLE[row.verdict] ?? "quiet"}`}>
                    {row.verdict}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 style={{ fontSize: "0.9rem", margin: "1rem 0 0.3rem" }}>
        Thermometers against each other
      </h3>
      <p className="lead">
        Three thermometers measure the same air. They are flagged when any pair differs by more
        than {number(thermometers.flag_threshold_c, 1)} °C.
      </p>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Pair</th>
              <th className="number">Average difference</th>
              <th className="number">Largest difference</th>
              <th className="number">Offset (first minus second)</th>
            </tr>
          </thead>
          <tbody>
            {thermometers.pairs.map((pair) => (
              <tr key={pair.pair}>
                <td>{pair.pair}</td>
                <td className="number">{number(pair.mean_abs_diff_c, 3)} °C</td>
                <td className="number">{number(pair.max_abs_diff_c, 3)} °C</td>
                <td className="number">
                  {signed.has(pair.pair) ? `${number(signed.get(pair.pair), 3)} °C` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
