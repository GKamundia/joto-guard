/** Local storage that cannot throw.
 *
 * Private browsing modes and blocked site data make these calls raise, and a preference is
 * never worth failing a render over: the page falls back to the default for the visit.
 */

export function read(key, fallback = null) {
  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

export function write(key, value) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // The choice then lasts for this visit only.
  }
}
