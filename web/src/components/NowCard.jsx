import { dayLabel, duration, hourOfDay, number } from "../format";
import { currentHour, easesAt, nextSpell, reach } from "../guidance";

const LEVEL_NAMES = {
  normal: "Normal",
  acclimatized_only: "Breaks for new workers",
  work_rest: "Breaks for everyone",
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

/* What each level asks of a crew. The minutes themselves are in the tiles beside this line,
   so the sentence names who has to change what, not the numbers again. */
const ACTIONS = {
  normal: "Work normally",
  acclimatized_only: "New workers need breaks",
  work_rest: "Everyone works in spells, resting in the shade",
  reschedule: "Too hot for this work",
};

/** What to do, and until when.
 *
 * English only: the guidance document's Kiswahili covers the levels and the standing advice,
 * and no reviewed wording exists for this sentence. It is shown below in Kiswahili as the
 * level sentence, which is reviewed.
 */
function Action({ level, spell, relief, now }) {
  // Normal counts down to the next hour that is worse; every other level counts down to
  // the hour it comes back to normal.
  const target = level === "normal" ? (spell?.from ?? null) : relief;
  const lead = ACTIONS[level] ?? ACTIONS.normal;
  const sentence = target
    ? `${lead} until ${hourOfDay(target.local_time)}.`
    : `${lead} for the rest of this forecast.`;
  const away = target ? Date.parse(target.hour_utc) - now : 0;

  return (
    <p className="now-action">
      {sentence}
      {away > 0 ? (
        <span className="now-countdown">
          {level === "normal" ? `${duration(away)} from now` : `eases in ${duration(away)}`}
        </span>
      ) : null}
    </p>
  );
}

export default function NowCard({ guidance, workType, now = Date.now() }) {
  const hour = currentHour(guidance.hours, now);
  if (!hour) return <OutOfDate guidance={guidance} />;

  const advice = hour.by_work_type[workType];
  const level = advice?.level ?? "normal";
  const spell = nextSpell(guidance.hours, workType, now);
  const relief = level === "normal" ? null : easesAt(guidance.hours, workType, now);
  const limit = guidance.work_types[workType];
  const mightRise = advice?.level_if_high && advice.level_if_high !== level;

  return (
    <section className={`card now level-${level}`}>
      <div className="now-grid">
        <div className="now-main">
          <p className="now-when">Right now · {hourOfDay(hour.local_time)} at the station</p>
          <p className="now-level">{LEVEL_NAMES[level]}</p>
          <Action level={level} spell={spell} relief={relief} now={now} />
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

      <p className="now-who">
        <strong>New workers</strong> are people new to working in the heat, or back after a week
        or more away. Most of a crew that works outdoors here every day is used to the heat.
      </p>

      <p className="now-next">
        {spell ? (
          <>
            Next care needed: <strong>{hourOfDay(spell.from.local_time)}</strong> to{" "}
            <strong>
              {spell.endsAt ? hourOfDay(spell.endsAt.local_time) : "the end of the forecast"}
            </strong>{" "}
            on {dayLabel(spell.from.local_time)} ({spell.hours} hour
            {spell.hours === 1 ? "" : "s"}). At worst: {LEVEL_NAMES[spell.worst].toLowerCase()}.
          </>
        ) : (
          <>Nothing above normal in the rest of the forecast for this work.</>
        )}
        {mightRise ? ` The upper band reaches ${LEVEL_NAMES[advice.level_if_high].toLowerCase()}.` : ""}
      </p>
    </section>
  );
}
