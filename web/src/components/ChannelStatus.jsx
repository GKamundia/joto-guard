import { Fragment } from "react";
import { dayOfMonth } from "../format";

export default function ChannelStatus({ rows, rules }) {
  const days = [...new Set(rows.map((row) => row.date_utc))];
  const groups = [...new Set(rows.map((row) => row.group))];
  const byCell = new Map(rows.map((row) => [`${row.group}|${row.date_utc}`, row]));
  const columns = `minmax(6.5rem, auto) repeat(${days.length}, minmax(0, 1fr))`;

  const explain = (cell) =>
    cell.rules.length
      ? `${cell.group} on ${cell.date_utc}: ${cell.status}: ${cell.rules
          .map((rule) => `${rule} ${rules[rule] ?? ""}`.trim())
          .join("; ")}`
      : `${cell.group} on ${cell.date_utc}: ${cell.status}`;

  return (
    <section className="card">
      <h2>Sensor groups, day by day</h2>
      <p className="lead">
        Each square is one group on one day. Hover or tap a square for the rules behind it.
      </p>

      <div className="scroll">
        <div className="matrix" style={{ gridTemplateColumns: columns }}>
          <div />
          {days.map((day) => (
            <div className="head" key={day} style={{ textAlign: "center" }}>
              {dayOfMonth(day)}
            </div>
          ))}
          {groups.map((group) => (
            <Fragment key={group}>
              <div className="head">{group.replace(/_/g, " ")}</div>
              {days.map((day) => {
                const cell = byCell.get(`${group}|${day}`);
                return (
                  <div
                    key={day}
                    className={`cell ${cell ? cell.status : "absent"}`}
                    title={cell ? explain(cell) : `${group} on ${day}: no data`}
                  />
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>

      <div className="legend">
        <span className="good">good</span>
        <span className="suspect">suspect</span>
        <span className="bad">bad</span>
      </div>
    </section>
  );
}
