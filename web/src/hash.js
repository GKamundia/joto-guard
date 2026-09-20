/** What the reader is looking at, carried in the URL.
 *
 * A supervisor sends "look at Sunday afternoon" to a foreman, so the tab, the kind of work and
 * the chosen day all have to survive being copied out of the address bar. The shape is
 * `#guidance?work=heavy&day=2026-09-20`.
 */

export function readHash(search = window.location.hash) {
  const [tab, query = ""] = search.replace(/^#/, "").split("?");
  const params = new URLSearchParams(query);
  return { tab, work: params.get("work"), day: params.get("day") };
}

export function writeHash({ tab, work, day }) {
  const params = new URLSearchParams();
  if (work) params.set("work", work);
  if (day) params.set("day", day);
  const query = params.toString();
  return query ? `${tab}?${query}` : tab;
}
