const BASE = (import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000").replace(/\/$/, "");

async function get(path) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`);
  } catch {
    throw new Error(
      `Cannot reach the Sentinel API at ${BASE}. Start it with: uvicorn api.app:app --reload`,
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `${path} returned ${response.status}`);
  }
  return response.json();
}

export const fetchStationHealth = () => get("/v1/station-health");

export const fetchHeatGuidance = () => get("/v1/heat-guidance");

export const fetchWbgt = (days = 7) => get(`/v1/wbgt?days=${days}`);

export const datasetUrl = (name) => `${BASE}/v1/dataset/${name}`;

export const apiDocsUrl = `${BASE}/docs`;
