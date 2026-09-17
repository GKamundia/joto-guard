export const isMissing = (value) => value === null || value === undefined || value === "";

export const number = (value, digits = 1) =>
  isMissing(value) ? "—" : Number(value).toFixed(digits);

export const count = (value) => (isMissing(value) ? "—" : Number(value).toLocaleString("en-GB"));

export const stamp = (iso) => (isMissing(iso) ? "—" : iso.replace("T", " ").replace("Z", " UTC"));

/** Counts stay whole, measurements keep up to three decimals without trailing zeros. */
export const measure = (value) => {
  if (isMissing(value)) return "—";
  return Number.isInteger(value) ? count(value) : String(Number(Number(value).toFixed(3)));
};

export const dayOfMonth = (date) => (isMissing(date) ? "" : date.slice(8));

export const monthDay = (date) => (isMissing(date) ? "—" : date.slice(5));
