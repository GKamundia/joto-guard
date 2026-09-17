import { apiDocsUrl, datasetUrl } from "../api";

const FILES = [
  ["obs_qc.csv", "Every observation with its quality flags"],
  ["obs_hourly.csv", "Hourly values built only from good and suspect observations"],
  ["health_daily.csv", "Daily health score and the groups behind it"],
  ["channel_status_daily.csv", "Status of each sensor group, day by day"],
  ["gaps.csv", "Interruptions longer than the gap threshold"],
  ["rule_hits.csv", "How often each rule fired, per channel and day"],
  ["audit_results.csv", "Checks of the station's calculated columns"],
  ["report.json", "This page as data"],
];

export default function Downloads() {
  return (
    <section className="card">
      <h2>Take the data</h2>
      <p className="lead">
        The quality-controlled tables behind this page, and the API that serves them.
      </p>
      <div className="scroll">
        <table>
          <tbody>
            {FILES.map(([name, description]) => (
              <tr key={name}>
                <td>
                  <a href={datasetUrl(name)}>{name}</a>
                </td>
                <td>{description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="lead" style={{ marginTop: "0.8rem", marginBottom: 0 }}>
        <a href={apiDocsUrl}>API documentation</a>
      </p>
    </section>
  );
}
