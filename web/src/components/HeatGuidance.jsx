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

const ADVICE_ORDER = [
  ["water", "Water."],
  ["new_workers", "New workers."],
  ["rest", "Rest."],
];

const MIN_HOURS_PER_DAY = 12;

function DaySummary({ day, workType, swahili, selected, onSelect }) {
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
    <button
      type="button"
      className={`guidance-day level-${summary.worst_level}${selected ? " selected" : ""}`}
      aria-pressed={selected}
      onClick={() => onSelect(selected ? null : day.date)}
    >
      <strong>{day.date}</strong>
      <span className="peak">
        up to {number(summary.peak_wbgt_c)} °C at {summary.peak_time}
      </span>
      <span>{advice}</span>
      <span className="sw" lang="sw">
        {swahili.levels[summary.worst_level]}
      </span>
    </button>
  );
}

function HourDetail({ hour, workType, guidance }) {
  const advice = hour.by_work_type[workType];
  return (
    <div className={`hour-detail level-${advice.level ?? "unknown"}`}>
      <h3>
        {hour.local_time} · {WORK_NAMES[workType]}
      </h3>
      <dl>
        <div>
          <dt>WBGT</dt>
          <dd>
            {number(hour.wbgt_c)} °C
            {hour.wbgt_low_c !== null ? (
              <small>
                {" "}
                likely {number(hour.wbgt_low_c)}–{number(hour.wbgt_high_c)}
              </small>
            ) : null}
          </dd>
        </div>
        <div>
          <dt>Level</dt>
          <dd>{LEVEL_NAMES[advice.level] ?? "—"}</dd>
        </div>
        <div>
          <dt>Used to the heat</dt>
          <dd>
            {advice.work_minutes_acclimatized ?? "—"} min<small> work per hour</small>
          </dd>
        </div>
        <div>
          <dt>New workers</dt>
          <dd>
            {advice.work_minutes_new_workers ?? "—"} min<small> work per hour</small>
          </dd>
        </div>
      </dl>
      <p>{guidance.levels[advice.level]}</p>
      <p className="sw" lang="sw">
        {guidance.swahili.levels[advice.level]}
      </p>
      {advice.level_if_high && advice.level_if_high !== advice.level ? (
        <p className="might">
          If the hour lands at the top of its band it becomes{" "}
          {LEVEL_NAMES[advice.level_if_high].toLowerCase()}.
        </p>
      ) : null}
    </div>
  );
}

export default function HeatGuidance({ guidance, workType, onWorkType, error }) {
  const [day, setDay] = useState(null);
  const [picked, setPicked] = useState(null);

  if (!guidance) {
    return (
      <section className="card">
        <h2>Heat guidance for outdoor work</h2>
        <p className="lead">{error ?? "Loading the forecast…"}</p>
      </section>
    );
  }

  const work = guidance.work_types[workType];
  const swahili = guidance.swahili;
  const now = Date.now();
  const hours = guidance.hours.filter((hour) => {
    if (day) return hour.local_time.startsWith(day);
    return Date.parse(hour.hour_utc) + 3600 * 1000 > now;
  });
  const shown = picked && hours.some((hour) => hour.hour_utc === picked.hour_utc) ? picked : null;

  return (
    <section className="card">
      <h2>Heat guidance for outdoor work</h2>
      <p className="lead">
        Hour by hour for the next days at the station, from the ECMWF forecast
        {guidance.forecast.corrected_towards_station
          ? " corrected towards the station's own readings"
          : ""}
        , judged against NIOSH's heat limits for the type of work.
      </p>

      <div className="worktypes" role="group" aria-label="Type of work">
        {Object.keys(guidance.work_types).map((name) => (
          <button
            key={name}
            type="button"
            className={name === workType ? "selected" : ""}
            aria-pressed={name === workType}
            onClick={() => onWorkType(name)}
          >
            {WORK_NAMES[name] ?? name}
            <small lang="sw">{swahili.work_types[name]}</small>
          </button>
        ))}
      </div>
      <p className="lead">
        For example: {work.examples.join("; ")}. Workers used to the heat can work without breaks up
        to {number(work.limit_acclimatized_c)} °C WBGT; new workers up to{" "}
        {number(work.limit_new_workers_c)} °C.
      </p>

      <div className="guidance-days">
        {guidance.days.map((item) => (
          <DaySummary
            key={item.date}
            day={item}
            workType={workType}
            swahili={swahili}
            selected={item.date === day}
            onSelect={setDay}
          />
        ))}
      </div>
      <p className="lead">
        {day ? (
          <>
            Showing {day}. <button type="button" className="link" onClick={() => setDay(null)}>
              Show the hours ahead instead
            </button>
          </>
        ) : (
          <>Showing the hours ahead. Choose a day above to see all of it.</>
        )}
      </p>

      <div className="hours" aria-label="Hourly levels">
        {hours.map((hour) => {
          const advice = hour.by_work_type[workType];
          const mightRise = advice.level_if_high && advice.level_if_high !== advice.level;
          const isShown = shown?.hour_utc === hour.hour_utc;
          return (
            <button
              key={hour.hour_utc}
              type="button"
              className={`hour level-${advice.level ?? "unknown"}${mightRise ? " might-rise" : ""}${
                isShown ? " selected" : ""
              }`}
              aria-pressed={isShown}
              onClick={() => setPicked(isShown ? null : hour)}
              title={`${hour.local_time}: ${number(hour.wbgt_c)} °C`}
            >
              <span>{hour.local_time.slice(11, 13)}</span>
              <strong>{number(hour.wbgt_c, 0)}</strong>
            </button>
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

      {shown ? <HourDetail hour={shown} workType={workType} guidance={guidance} /> : null}

      <ul className="advice">
        {ADVICE_ORDER.map(([key, label]) => (
          <li key={key}>
            <strong>{label}</strong> {guidance.advice[key]}
            <span className="sw" lang="sw">
              {swahili.advice[key]}
            </span>
          </li>
        ))}
      </ul>
      <p className="lead" style={{ marginTop: "0.6rem", marginBottom: 0 }}>
        Local hours, WBGT in °C. Choose an hour for its detail. Limits from NIOSH (2016), example
        tasks from the 2024 Compendium of Physical Activities.
      </p>
    </section>
  );
}
