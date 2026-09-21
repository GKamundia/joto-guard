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
  // `until` is the last hour in the spell; `endsAt` is the hour after it, which is when the
  // spell is over. Saying "11:00 to 17:00" and "until 17:00" means the same six hours, where
  // "to 16:00" beside "until 17:00" reads as a contradiction.
  const order = ["normal", "acclimatized_only", "work_rest", "reschedule"];
  const worst = ahead
    .slice(start, end + 1)
    .map((hour) => hour.by_work_type[workType].level)
    .reduce((a, b) => (order.indexOf(b) > order.indexOf(a) ? b : a));
  return {
    from: ahead[start],
    until: ahead[end],
    endsAt: ahead[end + 1] ?? null,
    hours: end - start + 1,
    worst,
  };
}

/** The hours still to come, in order. Empty once the forecast no longer reaches now. */
export function hoursAhead(hours, now = Date.now()) {
  return hours.filter((hour) => Date.parse(hour.hour_utc) + HOUR_MS > now);
}

/** The first hour back at normal from `from`. Only meaningful while the current hour is not. */
export function easesAt(hours, workType, from = Date.now()) {
  return (
    hours.find(
      (hour) =>
        Date.parse(hour.hour_utc) + HOUR_MS > from &&
        hour.by_work_type[workType]?.level === "normal",
    ) ?? null
  );
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
