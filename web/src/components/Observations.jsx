import { count, number, stamp } from "../format";

export default function Observations({ rain, light, codes }) {
  const rainDays = rain.daily.filter((day) => day.rain1_mm || day.rain2_mm);
  const zeroDays = new Map(rain.gauge_read_zero.map((row) => [row.date_utc, row.gauge]));

  return (
    <section className="card">
      <h2>Rain, light and device codes</h2>

      <h3 style={{ fontSize: "0.9rem", margin: "0.6rem 0 0.3rem" }}>Rain gauges</h3>
      {rainDays.length === 0 ? (
        <p className="lead">
          Neither gauge recorded rain over this record, so they cannot be compared.
        </p>
      ) : (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Day</th>
                <th className="number">Gauge 1</th>
                <th className="number">Gauge 2</th>
                <th>Agreement</th>
              </tr>
            </thead>
            <tbody>
              {rainDays.map((day) => (
                <tr key={day.date_utc}>
                  <td>{day.date_utc}</td>
                  <td className="number">{number(day.rain1_mm, 1)} mm</td>
                  <td className="number">{number(day.rain2_mm, 1)} mm</td>
                  <td>
                    {zeroDays.has(day.date_utc) ? (
                      <span className="pill suspect">
                        {zeroDays.get(day.date_utc) === "rain2_mm" ? "gauge 2" : "gauge 1"} read
                        zero
                      </span>
                    ) : (
                      <span className="pill good">both agree</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 style={{ fontSize: "0.9rem", margin: "1rem 0 0.3rem" }}>Light sensor</h3>
      <p className="lead">{light.note}</p>
      <dl className="facts">
        {Object.entries(light.night_counts).map(([channel, values]) => (
          <div key={channel}>
            <dt>{channel.replace(/_/g, " ")} at night</dt>
            <dd>
              median {number(values.median, 0)}, lowest {number(values.min, 0)} counts
            </dd>
          </div>
        ))}
        <div>
          <dt>Brightest day recorded</dt>
          <dd>
            {count(Math.max(...light.daily_max.map((day) => day.light_vis_counts ?? 0)))} counts
            visible
          </dd>
        </div>
        <div>
          <dt>Calibrated to W/m²</dt>
          <dd>{light.calibrated ? "yes" : "not yet"}</dd>
        </div>
      </dl>

      <h3 style={{ fontSize: "0.9rem", margin: "1rem 0 0.3rem" }}>Device health codes</h3>
      <p className="lead">
        {count(codes.rows_with_code_zero)} rows reported code 0. The station's other codes are not
        documented, so they are recorded without being judged.
      </p>
      {codes.codes.length > 0 && (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th className="number">Rows</th>
                <th className="number">Days</th>
                <th>First seen</th>
                <th>Last seen</th>
                <th className="number">Typical gap before it</th>
              </tr>
            </thead>
            <tbody>
              {codes.codes.map((code) => (
                <tr key={code.code}>
                  <td>{code.code}</td>
                  <td className="number">{count(code.rows)}</td>
                  <td className="number">{count(code.days_seen)}</td>
                  <td>{stamp(code.first_utc)}</td>
                  <td>{stamp(code.last_utc)}</td>
                  <td className="number">
                    {code.median_interval_before_s === null
                      ? "—"
                      : `${number(code.median_interval_before_s, 0)} s`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
