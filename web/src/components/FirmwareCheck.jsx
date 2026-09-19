import { number } from "../format";

const WIDTH = 24 * 14;
const PLOT = 90;
const LABELS = 14;
const SCALE = 10; // pixels per degree

export default function FirmwareCheck({ wbgt }) {
  if (!wbgt) return null;
  const rows = wbgt.firmware_by_local_hour;
  const midday = rows.filter((row) => row.local_hour >= 10 && row.local_hour <= 15);
  const middayGap =
    midday.reduce((sum, row) => sum + row.fw_minus_model_c * row.n_hours, 0) /
    midday.reduce((sum, row) => sum + row.n_hours, 0);

  return (
    <section className="card">
      <h2>The station's own WBGT column</h2>
      <p className="lead">
        The station reports a WBGT it works out itself. Against the standard model (Liljegren et
        al. 2008) run on the same sensors, it reads {number(Math.abs(middayGap))} °C lower from
        10:00 to 15:59: it behaves as if the sun were not shining, so it could not be used to warn
        anyone.
      </p>
      <svg className="chart" viewBox={`0 0 ${WIDTH} ${PLOT + LABELS}`} role="img">
        <title>Firmware WBGT minus the modelled WBGT, by local hour</title>
        <line className="grid" x1="0" x2={WIDTH} y1="2" y2="2" />
        {rows.map((row) => {
          const height = Math.abs(row.fw_minus_model_c) * SCALE;
          return (
            <g key={row.local_hour}>
              <rect className="bar below" x={row.local_hour * 14 + 2} y="2" width="10" height={height}>
                <title>
                  {String(row.local_hour).padStart(2, "0")}:00: {number(row.fw_minus_model_c)} °C
                  over {row.n_hours} hours
                </title>
              </rect>
              {row.local_hour % 3 === 0 && (
                <text x={row.local_hour * 14} y={PLOT + 10}>
                  {String(row.local_hour).padStart(2, "0")}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <p className="lead" style={{ marginTop: "0.6rem", marginBottom: 0 }}>
        Bars show how far the firmware's value sits below the model at each local hour, averaged
        over {wbgt.firmware_by_local_hour[0]?.n_hours ?? 0} days.
      </p>
    </section>
  );
}
