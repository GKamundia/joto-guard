/** Reading the guidance document: which hour we are in, what is coming, and how far it reaches. */

const HOUR_MS = 3600 * 1000;

/** The forecast hour we are in, or the next one if the record starts later. */
export function currentHour(hours, now = Date.now()) {
  return (
    hours.find((hour) => {
      const start = Date.parse(hour.hour_utc);
      return start <= now && now < start + HOUR_MS;
    }) ??
    hours.find((hour) => Date.parse(hour.hour_utc) > now) ??
    null
  );
}

/** The next run of hours at or above `level`, as local times, or null if there is none. */
export function nextSpell(hours, workType, from = Date.now()) {
  const ahead = hours.filter((hour) => Date.parse(hour.hour_utc) + HOUR_MS > from);
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

/** The hours still to come, in order. Empty once the forecast no longer reaches now. */
export function hoursAhead(hours, now = Date.now()) {
  return hours.filter((hour) => Date.parse(hour.hour_utc) + HOUR_MS > now);
}

/** When the document was written and how far its hours reach.
 *
 * A build carries the forecast that was current when its pipeline last ran, so a copy left
 * running long enough will outlive its own forecast. The page has to say so rather than
 * quietly drop the parts that need an hour.
 */
export function reach(guidance, now = Date.now()) {
  const last = guidance.hours.at(-1) ?? null;
  const endsAt = last ? Date.parse(last.hour_utc) + HOUR_MS : 0;
  return {
    issuedAt: guidance.generated_at_utc,
    last,
    endsAt,
    ranOut: endsAt <= now,
  };
}
