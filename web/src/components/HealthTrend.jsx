import { monthDay, number } from "../format";

const WIDTH = 900;
const PLOT = 150;
const LABELS = 22;
const AXIS = 26;

export default function HealthTrend({ health }) {
  const days = health.daily;
  // A fixed viewBox that the card scales to its own width, so the bars fill the space
  // whether the record is 13 days or 130.
  const slot = (WIDTH - AXIS) / Math.max(days.length, 1);
  const bar = Math.min(slot * 0.72, 28);
  const labelEvery = Math.ceil(days.length / 8);

  return (
    <section className="card">
      <h2>Daily health score</h2>
      <p className="lead">
        {days.length} day{days.length === 1 ? "" : "s"} covered, scoring{" "}
        {number(Math.min(...days.map((d) => d.score)), 1)} to{" "}
        {number(Math.max(...days.map((d) => d.score)), 1)} out of 100.
      </p>

      <svg className="chart" viewBox={`0 0 ${WIDTH} ${PLOT + LABELS}`} role="img">
        <title>Health score for each covered day</title>
        {[0, 50, 100].map((value) => (
          <g key={value}>
            <line
              className="grid"
              x1={AXIS}
              x2={WIDTH}
              y1={PLOT - value * 1.5}
              y2={PLOT - value * 1.5}
            />
            <text x="0" y={PLOT - value * 1.5 - 3}>
              {value}
            </text>
          </g>
        ))}
        {days.map((day, index) => (
          <g key={day.date_utc}>
            <rect
              className="bar"
              x={AXIS + index * slot + (slot - bar) / 2}
              y={PLOT - day.score * 1.5}
              width={bar}
              height={Math.max(day.score * 1.5, 0.5)}
            >
              <title>
                {day.date_utc}: {day.score}
                {day.bad_groups.length ? ` · bad: ${day.bad_groups.join(", ")}` : ""}
                {day.suspect_groups.length ? ` · suspect: ${day.suspect_groups.join(", ")}` : ""}
              </title>
            </rect>
            {index % labelEvery === 0 && (
              <text x={AXIS + index * slot} y={PLOT + 15}>
                {monthDay(day.date_utc)}
              </text>
            )}
          </g>
        ))}
      </svg>

      <p className="note">
        {health.rule}
      </p>
    </section>
  );
}
