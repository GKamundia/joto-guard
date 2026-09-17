import { count, number, stamp } from "../format";

export default function CoverageCalendar({ coverage }) {
  const { daily, gaps, export_windows: windows } = coverage;
  return (
    <section className="card">
      <h2>Coverage</h2>
      <p className="lead">
        Observations received each day, out of the 1,440 a one-minute cadence would give. Days no
        export covers are left out rather than counted as an outage.
      </p>

      <div className="days">
        {daily.map((day) => (
          <div className="day" key={day.date_utc}>
            <strong>{day.date_utc.slice(5)}</strong>
            <span className="score">{number(day.coverage_pct, 0)}%</span>
            <div>{count(day.n_obs)} obs</div>
            {day.missing_minutes > 0 && <div>{number(day.missing_minutes, 1)} min missing</div>}
          </div>
        ))}
      </div>

      <h3 style={{ fontSize: "0.9rem", margin: "1rem 0 0.3rem" }}>Periods the exports cover</h3>
      <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.85rem" }}>
        {windows.map((window) => (
          <li key={window.start_utc}>
            {stamp(window.start_utc)} to {stamp(window.end_utc)}
          </li>
        ))}
      </ul>

      <h3 style={{ fontSize: "0.9rem", margin: "1rem 0 0.3rem" }}>
        Interruptions ({coverage.reporting_gaps} in reporting, {coverage.gaps_between_exports}{" "}
        between exports, {coverage.late_intervals} late reports)
      </h3>
      {gaps.length === 0 ? (
        <p className="lead" style={{ marginBottom: 0 }}>
          No interval longer than {coverage.gap_threshold_s} s.
        </p>
      ) : (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>From</th>
                <th>To</th>
                <th className="number">Minutes</th>
                <th>Kind</th>
              </tr>
            </thead>
            <tbody>
              {gaps.map((gap) => (
                <tr key={gap.gap_end_utc}>
                  <td>{stamp(gap.gap_start_utc)}</td>
                  <td>{stamp(gap.gap_end_utc)}</td>
                  <td className="number">{number(gap.missing_minutes, 1)}</td>
                  <td>
                    {gap.kind === "reporting" ? (
                      <span className="pill suspect">station missed reports</span>
                    ) : (
                      <span className="pill quiet">not exported</span>
                    )}
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
