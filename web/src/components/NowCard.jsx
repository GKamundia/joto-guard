import { dayLabel, hourOfDay, number } from "../format";
import { currentHour, nextSpell, reach } from "../guidance";

const LEVEL_NAMES = {
  normal: "Normal",
  acclimatized_only: "Acclimatized only",
  work_rest: "Work/rest",
  reschedule: "Reschedule",
};

/** Shown when the build's forecast no longer reaches the present. */
function OutOfDate({ guidance }) {
  const { issuedAt, last } = reach(guidance);
  return (
    <section className="card now out-of-date">
      <p className="now-when">No guidance for right now</p>
      <p className="now-level">This forecast has run out</p>
      <p className="now-sentence">
        It was issued on {dayLabel(issuedAt)} and its last hour is {hourOfDay(last.local_time)} on{" "}
        {dayLabel(last.local_time)}. The days below are the ones it covered. The station record and
        its health report do not depend on it and are unaffected.
      </p>
      <p className="now-next">
        Refresh it with <code>python -m joto_guard forecast</code>, or start the stack with{" "}
        <code>docker compose up --build</code>, which refreshes the forecast before serving.
      </p>
    </section>
  );
}

export default function NowCard({ guidance, workType }) {
  const hour = currentHour(guidance.hours);
  if (!hour) return <OutOfDate guidance={guidance} />;

  const advice = hour.by_work_type[workType];
  const level = advice?.level ?? "normal";
  const spell = nextSpell(guidance.hours, workType);
  const limit = guidance.work_types[workType];
  const mightRise = advice?.level_if_high && advice.level_if_high !== level;

  return (
    <section className={`card now level-${level}`}>
      <div className="now-grid">
        <div className="now-main">
          <p className="now-when">Right now · {hourOfDay(hour.local_time)} at the station</p>
          <p className="now-level">{LEVEL_NAMES[level]}</p>
          <p className="now-reading">
            <strong>{number(hour.wbgt_c)} °C</strong> WBGT
            {hour.wbgt_low_c !== null
              ? ` · likely ${number(hour.wbgt_low_c)}–${number(hour.wbgt_high_c)}`
              : ""}
          </p>
          <p className="now-sentence">{guidance.levels[level]}</p>
          <p className="now-sentence sw" lang="sw">
            {guidance.swahili.levels[level]}
          </p>
        </div>

        <dl className="now-facts">
          <div>
            <dt>Work in this hour</dt>
            <dd>
              {advice?.work_minutes_acclimatized ?? "-"} min
              <small>used to the heat</small>
            </dd>
          </div>
          <div>
            <dt>New workers</dt>
            <dd>
              {advice?.work_minutes_new_workers ?? "-"} min
              <small>in this hour</small>
            </dd>
          </div>
          <div>
            <dt>Limit for this work</dt>
            <dd>
              {number(limit.limit_acclimatized_c)} °C
              <small>{number(limit.limit_new_workers_c)} °C when new</small>
            </dd>
          </div>
        </dl>
      </div>

      <p className="now-next">
        {spell ? (
          <>
            Next care needed: <strong>{hourOfDay(spell.from.local_time)}</strong> to{" "}
            <strong>{hourOfDay(spell.until.local_time)}</strong> on{" "}
            {dayLabel(spell.until.local_time)}, {spell.hours} hour
            {spell.hours === 1 ? "" : "s"} at{" "}
            {LEVEL_NAMES[spell.from.by_work_type[workType].level].toLowerCase()} or worse.
          </>
        ) : (
          <>Nothing above normal in the rest of the forecast for this work.</>
        )}
        {mightRise ? ` The upper band reaches ${LEVEL_NAMES[advice.level_if_high].toLowerCase()}.` : ""}
      </p>
    </section>
  );
}
