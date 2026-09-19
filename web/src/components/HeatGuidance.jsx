import { useState } from "react";
import { number } from "../format";

const WORK_NAMES = {
  light: "Light work",
  moderate: "Moderate work",
  heavy: "Heavy work",
  very_heavy: "Very heavy work",
};

const LEVEL_NAMES = {
  normal: "Normal",
  acclimatized_only: "Acclimatized only",
  work_rest: "Work/rest",
  reschedule: "Reschedule",
};

const MIN_HOURS_PER_DAY = 12;
const HOURS_SHOWN = 48;

function hourTitle(hour, advice) {
  const parts = [`${hour.local_time}: WBGT ${number(hour.wbgt_c)} °C`];
  if (hour.wbgt_low_c !== null) {
    parts.push(`likely ${number(hour.wbgt_low_c)} to ${number(hour.wbgt_high_c)} °C`);
  }
  if (advice.level) {
    parts.push(LEVEL_NAMES[advice.level]);
    parts.push(`acclimatized: ${advice.work_minutes_acclimatized} min work per hour`);
    parts.push(`new workers: ${advice.work_minutes_new_workers} min`);
  }
  if (advice.level_if_high && advice.level_if_high !== advice.level) {
    parts.push(`could reach ${LEVEL_NAMES[advice.level_if_high].toLowerCase()}`);
  }
  return parts.join(" · ");
}

function DaySummary({ day, workType }) {
  const summary = day.by_work_type[workType];
  if (!summary || summary.hours < MIN_HOURS_PER_DAY) return null;
  let advice = "No limit reached.";
  if (summary.limited_from) {
    advice = `Acclimatized workers need breaks from ${summary.limited_from} to ${summary.limited_until}.`;
  } else if (summary.hours_acclimatized_only > 0) {
    advice = `New workers need breaks for ${summary.hours_acclimatized_only} hour${
      summary.hours_acclimatized_only === 1 ? "" : "s"
    }.`;
  }
  return (
    <div className={`guidance-day level-${summary.worst_level}`}>
      <strong>{day.date}</strong>
      <span className="peak">
        up to {number(summary.peak_wbgt_c)} °C at {summary.peak_time}
      </span>
      <span>{advice}</span>
    </div>
  );
}

export default function HeatGuidance({ guidance, error }) {
  const [workType, setWorkType] = useState("heavy");

  if (!guidance) {
    return (
      <section className="card">
        <h2>Heat guidance for outdoor work</h2>
        <p className="lead">{error ?? "Loading the forecast…"}</p>
      </section>
    );
  }

  const work = guidance.work_types[workType];
  const now = Date.now();
  const hours = guidance.hours
    .filter((hour) => Date.parse(hour.hour_utc) + 3600 * 1000 > now)
    .slice(0, HOURS_SHOWN);
  const corrected = guidance.forecast.corrected_towards_station;

  return (
    <section className="card">
      <h2>Heat guidance for outdoor work</h2>
      <p className="lead">
        Hour by hour for the next days at the station, from the ECMWF forecast
        {corrected ? " corrected towards the station's own readings" : ""}, judged against NIOSH's
        heat limits for the type of work.
      </p>

      <div className="worktypes" role="group" aria-label="Type of work">
        {Object.keys(guidance.work_types).map((name) => (
          <button
            key={name}
            type="button"
            className={name === workType ? "selected" : ""}
            onClick={() => setWorkType(name)}
          >
            {WORK_NAMES[name] ?? name}
          </button>
        ))}
      </div>
      <p className="lead">
        For example: {work.examples.join("; ")}. Workers used to the heat can work without breaks
        up to {number(work.limit_acclimatized_c)} °C WBGT; new workers up to{" "}
        {number(work.limit_new_workers_c)} °C.
      </p>

      <div className="guidance-days">
        {guidance.days.map((day) => (
          <DaySummary key={day.date} day={day} workType={workType} />
        ))}
      </div>

      <div className="hours" aria-label="Hourly levels">
        {hours.map((hour) => {
          const advice = hour.by_work_type[workType];
          const mightRise = advice.level_if_high && advice.level_if_high !== advice.level;
          return (
            <div
              key={hour.hour_utc}
              className={`hour level-${advice.level ?? "unknown"}${mightRise ? " might-rise" : ""}`}
              title={hourTitle(hour, advice)}
            >
              <span>{hour.local_time.slice(11, 13)}</span>
              <strong>{number(hour.wbgt_c, 0)}</strong>
            </div>
          );
        })}
      </div>
      <div className="legend">
        {Object.entries(LEVEL_NAMES).map(([level, name]) => (
          <span key={level} className={`level-${level}`}>
            {name}
          </span>
        ))}
        <span className="might-rise">could reach the next level</span>
      </div>

      <ul className="advice">
        <li>
          <strong>Water.</strong> {guidance.advice.water}
        </li>
        <li>
          <strong>New workers.</strong> {guidance.advice.new_workers}
        </li>
        <li>
          <strong>Rest.</strong> {guidance.advice.rest}
        </li>
      </ul>
      <p className="lead" style={{ marginTop: "0.6rem", marginBottom: 0 }}>
        Local hours, WBGT in °C. Tap or hover an hour for the minutes of work allowed per hour.
        Limits from NIOSH (2016), example tasks from the 2024 Compendium of Physical Activities.
      </p>
    </section>
  );
}
