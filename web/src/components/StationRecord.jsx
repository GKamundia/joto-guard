import { useState } from "react";
import TimeSeries from "../charts/TimeSeries";
import { count, number } from "../format";

const MEASURES = [
  { key: "wbgt_c", name: "WBGT", unit: "°C", compare: "wbgt_fw_c", compareName: "firmware" },
  { key: "t_air_c", name: "Air temperature", unit: "°C" },
  { key: "rh_pct", name: "Humidity", unit: "%" },
  { key: "wind_2m_ms", name: "Wind at 2 m", unit: "m/s" },
  { key: "ghi_wm2", name: "Solar", unit: "W/m²" },
  { key: "tg_c", name: "Globe temperature", unit: "°C" },
  { key: "tnwb_c", name: "Natural wet bulb", unit: "°C" },
];

const TIMEZONE = "Africa/Nairobi";

const label = (iso, withDate) =>
  new Date(iso).toLocaleString("en-GB", {
    timeZone: TIMEZONE,
    ...(withDate ? { day: "2-digit", month: "short" } : {}),
    hour: "2-digit",
    minute: "2-digit",
  });

export default function StationRecord({ wbgt, failure }) {
  const [measure, setMeasure] = useState("wbgt_c");

  if (failure) return <p className="notice">The station record is not available. {failure}</p>;
  if (!wbgt) return <p className="notice">Loading the station record…</p>;

  const chosen = MEASURES.find((item) => item.key === measure);
  const toPoints = (key) =>
    wbgt.hours.map((hour) => ({
      x: Date.parse(hour.hour_utc),
      y: hour[key],
      label: label(hour.hour_utc, false),
      full: label(hour.hour_utc, true),
    }));

  const measured = wbgt.hours.filter((hour) => hour.wbgt_c !== null).length;
  const warmest = wbgt.hours.reduce(
    (best, hour) => (hour.wbgt_c !== null && (!best || hour.wbgt_c > best.wbgt_c) ? hour : best),
    null,
  );
  const held = wbgt.light_calibration.held_out;

  return (
    <>
      <section className="card">
        <h2>What the station recorded</h2>
        <p className="lead">
          Every hour of the record, built only from observations that passed quality control.{" "}
          <strong>{count(measured)}</strong> of {count(wbgt.hours.length)} hours have a complete set
          of inputs; the rest are left empty rather than filled, which is why the line breaks. The
          warmest hour was{" "}
          <strong>
            {number(warmest?.wbgt_c)} °C on {warmest ? label(warmest.hour_utc, true) : "—"}
          </strong>
          .
        </p>

        <div className="worktypes" role="group" aria-label="Measurement">
          {MEASURES.map((item) => (
            <button
              key={item.key}
              type="button"
              className={item.key === measure ? "selected" : ""}
              onClick={() => setMeasure(item.key)}
            >
              {item.name}
            </button>
          ))}
        </div>

        <TimeSeries
          name={chosen.name}
          points={toPoints(chosen.key)}
          compare={chosen.compare ? toPoints(chosen.compare) : null}
          compareName={chosen.compareName}
          unit={chosen.unit}
        />
        {chosen.compare ? (
          <p className="series-legend">
            <span className="key main" /> our model
            <span className="key compare" /> the station's own column
          </p>
        ) : null}
        <p className="lead" style={{ marginTop: "0.6rem", marginBottom: 0 }}>
          Method: {wbgt.method}.
        </p>
      </section>

      <section className="card">
        <h2>Turning the light sensor into W/m²</h2>
        <p className="lead">
          The SI1145 reports raw counts, and the WBGT model needs irradiance. Fitted against ERA5,
          each day left out of its own fit in turn.
        </p>
        <p className="formula">{wbgt.light_calibration.formula}</p>
        <table className="grid">
          <thead>
            <tr>
              <th>Hours</th>
              <th>n</th>
              <th>RMSE</th>
              <th>Bias</th>
              <th>R²</th>
            </tr>
          </thead>
          <tbody>
            {[
              ["All daylight", held.daylight],
              ["Sun above 30°", held.high_sun],
              ["Clear reference sky", held.clear_reference_sky],
            ].map(([name, row]) => (
              <tr key={name}>
                <th scope="row">{name}</th>
                <td>{count(row.n_hours)}</td>
                <td>{number(row.rmse_wm2, 0)} W/m²</td>
                <td>{number(row.bias_wm2, 0)} W/m²</td>
                <td>{number(row.r2, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="lead" style={{ marginTop: "0.7rem", marginBottom: 0 }}>
          This is the weakest link in the chain and we would rather say so. The station sees its own
          cloud while ERA5 averages a 25 km cell, which is most of the gap: under a clear reference
          sky the error halves. Still, an error of that size moves WBGT by about ±1.2 °C at midday,
          and the NIOSH limits are only 1.5 to 3 °C apart.
        </p>
      </section>
    </>
  );
}
