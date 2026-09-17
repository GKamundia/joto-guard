import { monthDay, number } from "../format";

const BAR = 10;
const GAP = 3;
const PLOT = 100;
const LABELS = 16;
const AXIS = 14;

export default function HealthTrend({ health }) {
  const days = health.daily;
  const width = AXIS + days.length * (BAR + GAP);
  const labelEvery = Math.ceil(days.length / 5);

  return (
    <section className="card">
      <h2>Daily health score</h2>
      <p className="lead">
        {days.length} day{days.length === 1 ? "" : "s"} covered, scoring{" "}
        {number(Math.min(...days.map((d) => d.score)), 1)} to{" "}
        {number(Math.max(...days.map((d) => d.score)), 1)} out of 100.
      </p>

      <svg className="chart" viewBox={`0 0 ${width} ${PLOT + LABELS}`} role="img">
        <title>Health score for each covered day</title>
        {[0, 50, 100].map((value) => (
          <g key={value}>
            <line className="grid" x1={AXIS} x2={width} y1={PLOT - value} y2={PLOT - value} />
            <text x="0" y={PLOT - value - 2}>
              {value}
            </text>
          </g>
        ))}
        {days.map((day, index) => (
          <g key={day.date_utc}>
            <rect
              className="bar"
              x={AXIS + index * (BAR + GAP)}
              y={PLOT - day.score}
              width={BAR}
              height={Math.max(day.score, 0.5)}
            >
              <title>
                {day.date_utc}: {day.score}
                {day.bad_groups.length ? ` · bad: ${day.bad_groups.join(", ")}` : ""}
                {day.suspect_groups.length ? ` · suspect: ${day.suspect_groups.join(", ")}` : ""}
              </title>
            </rect>
            {index % labelEvery === 0 && (
              <text x={AXIS + index * (BAR + GAP)} y={PLOT + 10}>
                {monthDay(day.date_utc)}
              </text>
            )}
          </g>
        ))}
      </svg>

      <p className="lead" style={{ marginTop: "0.6rem", marginBottom: 0 }}>
        {health.rule}
      </p>
    </section>
  );
}
