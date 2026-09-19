import { number } from "../format";

const LEVEL_NAMES = {
  normal: "Normal",
  acclimatized_only: "Acclimatized only",
  work_rest: "Work/rest",
  reschedule: "Reschedule",
};

/** The forecast hour we are in, or the next one if the record starts later. */
export function currentHour(hours, now = Date.now()) {
  return (
    hours.find((hour) => {
      const start = Date.parse(hour.hour_utc);
      return start <= now && now < start + 3600 * 1000;
    }) ??
    hours.find((hour) => Date.parse(hour.hour_utc) > now) ??
    null
  );
}

/** The next run of hours at or above `level`, as local times, or null if there is none. */
export function nextSpell(hours, workType, from = Date.now()) {
  const ahead = hours.filter((hour) => Date.parse(hour.hour_utc) + 3600 * 1000 > from);
  const start = ahead.findIndex((hour) => {
    const level = hour.by_work_type[workType]?.level;
    return level && level !== "normal";
  });
  if (start < 0) return null;
  let end = start;
  while (
    end + 1 < ahead.length &&
    ahead[end + 1].by_work_type[workType]?.level &&
    ahead[end + 1].by_work_type[workType].level !== "normal"
  ) {
    end += 1;
  }
  return { from: ahead[start], until: ahead[end], hours: end - start + 1 };
}

export default function NowCard({ guidance, workType }) {
  const hour = currentHour(guidance.hours);
  if (!hour) return null;

  const advice = hour.by_work_type[workType];
  const level = advice?.level ?? "normal";
  const spell = nextSpell(guidance.hours, workType);
  const limit = guidance.work_types[workType];
  const mightRise = advice?.level_if_high && advice.level_if_high !== level;

  return (
    <section className={`card now level-${level}`}>
      <div className="now-grid">
        <div className="now-main">
          <p className="now-when">Right now · {hour.local_time.slice(11)} at the station</p>
          <p className="now-level">{LEVEL_NAMES[level]}</p>
          <p className="now-sentence">{guidance.levels[level]}</p>
          <p className="now-sentence sw" lang="sw">
            {guidance.swahili.levels[level]}
          </p>
        </div>

        <dl className="now-facts">
          <div>
            <dt>WBGT</dt>
            <dd>
              {number(hour.wbgt_c)} °C
              {hour.wbgt_low_c !== null ? (
                <small>
                  {" "}
                  ({number(hour.wbgt_low_c)}–{number(hour.wbgt_high_c)})
                </small>
              ) : null}
            </dd>
          </div>
          <div>
            <dt>Work in this hour</dt>
            <dd>
              {advice?.work_minutes_acclimatized ?? "—"} min
              <small> used to the heat</small>
            </dd>
          </div>
          <div>
            <dt>New workers</dt>
            <dd>
              {advice?.work_minutes_new_workers ?? "—"} min
              <small> in this hour</small>
            </dd>
          </div>
          <div>
            <dt>Limit for this work</dt>
            <dd>
              {number(limit.limit_acclimatized_c)} °C
              <small> {number(limit.limit_new_workers_c)} °C when new</small>
            </dd>
          </div>
        </dl>
      </div>

      <p className="now-next">
        {spell ? (
          <>
            Next care needed: <strong>{spell.from.local_time.slice(11)}</strong> to{" "}
            <strong>{spell.until.local_time.slice(11)}</strong> on {spell.until.local_time.slice(0, 10)},{" "}
            {spell.hours} hour{spell.hours === 1 ? "" : "s"} at{" "}
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
