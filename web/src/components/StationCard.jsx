import { count, number, stamp } from "../format";

function Fact({ label, children }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export default function StationCard({ station, generatedAt, version }) {
  const interval = station.interval_s;
  return (
    <section className="card">
      <h2>Station</h2>
      <p className="lead">
        {station.name} · {station.site}
      </p>
      <dl className="facts">
        <Fact label="CHORDS instrument">{station.station_id}</Fact>
        <Fact label="Position">
          {number(station.latitude, 6)}, {number(station.longitude, 6)}
        </Fact>
        <Fact label="Elevation">{number(station.elevation_m, 1)} m</Fact>
        <Fact label="Observations">{count(station.n_obs)}</Fact>
        <Fact label="Record starts">{stamp(station.record_start_utc)}</Fact>
        <Fact label="Record ends">{stamp(station.record_end_utc)}</Fact>
        <Fact label="Reporting interval">
          {number(interval.median, 0)} s typical ({number(interval.min, 0)} to{" "}
          {number(interval.max, 0)} s)
        </Fact>
        <Fact label="Repeated timestamps removed">{count(station.duplicates_removed)}</Fact>
      </dl>

      <h3 style={{ fontSize: "0.9rem", margin: "1rem 0 0.3rem" }}>Files read</h3>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Export</th>
              <th className="number">Rows</th>
              <th>Covers</th>
              <th>Measurement count</th>
            </tr>
          </thead>
          <tbody>
            {station.source_files.map((file) => (
              <tr key={file.name}>
                <td style={{ wordBreak: "break-all" }}>{file.name}</td>
                <td className="number">{count(file.rows)}</td>
                <td>
                  {stamp(file.first_utc)} to {stamp(file.last_utc)}
                </td>
                <td>
                  {file.measurements_declared === file.measurements_counted ? (
                    <span className="pill good">matches header</span>
                  ) : (
                    <span className="pill bad">
                      header says {count(file.measurements_declared)}, file holds{" "}
                      {count(file.measurements_counted)}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="lead" style={{ marginTop: "0.9rem", marginBottom: 0 }}>
        Data attributed to {station.attribution}. Served through the CHORDS platform (
        <a href={station.chords_doi}>software DOI</a>, not a DOI for this data). Report built by
        Conduit Sentinel {version} at {stamp(generatedAt)}.
      </p>
    </section>
  );
}
