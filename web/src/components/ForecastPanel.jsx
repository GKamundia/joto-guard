import { useState } from "react";
import TimeSeries from "../charts/TimeSeries";
import { number } from "../format";

const MEASURES = [
  { key: "t_air_c", name: "Air temperature", unit: "°C" },
  { key: "rh_pct", name: "Humidity", unit: "%" },
  { key: "wind_2m_ms", name: "Wind at 2 m", unit: "m/s" },
  { key: "ghi_wm2", name: "Solar", unit: "W/m²" },
  { key: "tg_c", name: "Globe temperature", unit: "°C" },
  { key: "tnwb_c", name: "Natural wet bulb", unit: "°C" },
];

const label = (iso, timezone) =>
  new Date(iso).toLocaleString("en-GB", {
    timeZone: timezone,
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

const shortLabel = (iso, timezone) =>
  new Date(iso).toLocaleString("en-GB", { timeZone: timezone, hour: "2-digit", minute: "2-digit" });

function toPoints(hours, key, timezone) {
  return hours.map((hour) => ({
    x: Date.parse(hour.hour_utc),
    y: hour[key],
    label: shortLabel(hour.hour_utc, timezone),
    full: label(hour.hour_utc, timezone),
  }));
}

export default function ForecastPanel({ forecast, failure, guidance, workType }) {
  const [showRaw, setShowRaw] = useState(true);
  const [measure, setMeasure] = useState("t_air_c");

  if (failure) return <p className="notice">The forecast is not available. {failure}</p>;
  if (!forecast) return <p className="notice">Loading the forecast…</p>;

  const timezone = forecast.timezone;
  const corrected = toPoints(forecast.hours, "wbgt_corrected_c", timezone);
  const raw = toPoints(forecast.hours, "wbgt_c", timezone);
  const band = forecast.hours.map((hour) => ({
    x: Date.parse(hour.hour_utc),
    low: hour.wbgt_low_c,
    high: hour.wbgt_high_c,
  }));

  const limit = guidance?.work_types?.[workType];
  const thresholds = limit
    ? [
        { value: limit.limit_acclimatized_c, label: "used to the heat", kind: "warn" },
        { value: limit.limit_new_workers_c, label: "new workers", kind: "note" },
      ]
    : [];

  const skill = forecast.correction.held_out;
  const fitted = forecast.correction.fitted_on;

  return (
    <>
      <section className="card">
        <h2>WBGT for the next three days</h2>
        <p className="lead">
          {forecast.model.toUpperCase().replace("_", " ")} through Open-Meteo, corrected towards the
          station hour by hour. The shaded band is where the station's own value has fallen around
          this forecast on days left out of the fit. The dashed lines are the NIOSH limits for the
          work type chosen on the Guidance tab.
        </p>

        <div className="worktypes" role="group" aria-label="Series">
          <button
            type="button"
            className={showRaw ? "selected" : ""}
            onClick={() => setShowRaw((on) => !on)}
            aria-pressed={showRaw}
          >
            Raw forecast
            <small>{showRaw ? "shown" : "hidden"}</small>
          </button>
        </div>

        <TimeSeries
          name="Corrected WBGT"
          points={corrected}
          band={band}
          compare={showRaw ? raw : null}
          compareName="raw"
          thresholds={thresholds}
          onHover={() => {}}
        />
        <p className="series-legend">
          <span className="key main" /> corrected
          {showRaw ? (
            <>
              <span className="key compare" /> raw forecast
            </>
          ) : null}
          <span className="key band" /> where the station usually falls
        </p>
      </section>

      <section className="card">
        <h2>How much the correction helps</h2>
        <p className="lead">
          Fitted on {fitted.n_days} days ({fitted.first_day} to {fitted.last_day},{" "}
          {fitted.n_pairs.toLocaleString("en-GB")} hourly pairs). Every figure below comes from
          leaving a day out of the fit and then predicting it, so none of it is scored on data the
          correction had seen. "The station's usual value" is the fairest baseline: what you would
          guess from the station's own average for that hour of day, with no forecast at all.
        </p>
        <table className="grid">
          <thead>
            <tr>
              <th>Hours</th>
              <th>Raw forecast</th>
              <th>Corrected</th>
              <th>The station's usual value</th>
            </tr>
          </thead>
          <tbody>
            {[
              ["All hours", skill.all],
              ["Midday (10:00–15:59)", skill.midday],
            ].map(([name, row]) => (
              <tr key={name}>
                <th scope="row">{name}</th>
                <td>{number(row.raw.mae_c, 2)} °C</td>
                <td className="best">{number(row.corrected.mae_c, 2)} °C</td>
                <td>{number(row.station_usual.mae_c, 2)} °C</td>
              </tr>
            ))}
            {Object.entries(skill.by_lead_day).map(([lead, row]) => (
              <tr key={lead}>
                <th scope="row">
                  {lead === "0" ? "Same day" : `${lead} day${lead === "1" ? "" : "s"} ahead`}
                </th>
                <td>{number(row.raw.mae_c, 2)} °C</td>
                <td className="best">{number(row.corrected.mae_c, 2)} °C</td>
                <td>{number(row.station_usual.mae_c, 2)} °C</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="lead" style={{ marginTop: "0.7rem", marginBottom: 0 }}>
          Mean absolute error, lower is better. The correction beats both the raw forecast and the
          baseline at every lead day. Its band held the station on{" "}
          <strong>{number(skill.band_held_station_pct, 1)} %</strong> of hours, a little short of
          the 80 % it aims for, so treat a level near a boundary as uncertain.
        </p>
      </section>

      <section className="card">
        <h2>The weather behind the index</h2>
        <p className="lead">
          WBGT is not a temperature. It is a heat balance: these are the forecast inputs the model
          solves it from, for the same hours.
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
          name={MEASURES.find((m) => m.key === measure).name}
          points={toPoints(forecast.hours, measure, timezone)}
          unit={MEASURES.find((m) => m.key === measure).unit}
          height={200}
        />
      </section>
    </>
  );
}
