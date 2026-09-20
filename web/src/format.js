const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export const isMissing = (value) => value === null || value === undefined || value === "";

export const number = (value, digits = 1) =>
  isMissing(value) ? "-" : Number(value).toFixed(digits);

export const count = (value) => (isMissing(value) ? "-" : Number(value).toLocaleString("en-GB"));

export const stamp = (iso) => (isMissing(iso) ? "-" : iso.replace("T", " ").replace("Z", " UTC"));

/** Counts stay whole, measurements keep up to three decimals without trailing zeros. */
export const measure = (value) => {
  if (isMissing(value)) return "-";
  return Number.isInteger(value) ? count(value) : String(Number(Number(value).toFixed(3)));
};

export const dayOfMonth = (date) => (isMissing(date) ? "" : date.slice(8));

export const monthDay = (date) => (isMissing(date) ? "-" : date.slice(5));

/** "28 Aug" from the date part as written, so a reader's own zone cannot shift the day. */
export const shortDay = (date) => {
  if (isMissing(date)) return "-";
  const [, month, day] = date.slice(0, 10).split("-");
  return `${Number(day)} ${MONTHS[Number(month) - 1] ?? month}`;
};

/** "Sat 19 Sep". Guidance dates are already local to the station. */
export const dayLabel = (date) => {
  if (isMissing(date)) return "-";
  const [year, month, day] = date.slice(0, 10).split("-").map(Number);
  const weekday = WEEKDAYS[new Date(Date.UTC(year, month - 1, day)).getUTCDay()];
  return `${weekday} ${day} ${MONTHS[month - 1]}`;
};

/** The hour a local timestamp falls in, as "14:00". */
export const hourOfDay = (localTime) => (isMissing(localTime) ? "-" : localTime.slice(11, 16));

/** A gap ahead, as "2 h 40 min". Anything under a minute is not worth counting down. */
export const duration = (ms) => {
  const minutes = Math.round(ms / 60000);
  if (minutes < 1) return "under a minute";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest} min`;
  if (rest === 0) return `${hours} h`;
  return `${hours} h ${rest} min`;
};
