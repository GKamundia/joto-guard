import { useEffect, useState } from "react";
import { fetchForecast, fetchHeatGuidance, fetchStationHealth, fetchWbgt } from "./api";
import Audits from "./components/Audits";
import ChannelStatus from "./components/ChannelStatus";
import CoverageCalendar from "./components/CoverageCalendar";
import Downloads from "./components/Downloads";
import FirmwareCheck from "./components/FirmwareCheck";
import ForecastPanel from "./components/ForecastPanel";
import HealthTrend from "./components/HealthTrend";
import HeatGuidance from "./components/HeatGuidance";
import Method from "./components/Method";
import NowCard from "./components/NowCard";
import Observations from "./components/Observations";
import Recommendations from "./components/Recommendations";
import StationCard from "./components/StationCard";
import StationMap from "./components/StationMap";
import StationRecord from "./components/StationRecord";

const TABS = [
  ["guidance", "Guidance"],
  ["forecast", "Forecast"],
  ["station", "Station record"],
  ["health", "Station health"],
  ["method", "Method"],
];

/** One fetch per endpoint, kept together so every tab reads the same load.
 *
 * A tab whose own endpoint failed says so rather than waiting for ever; only the two the
 * whole page needs take it down.
 */
function useJotoData() {
  const [data, setData] = useState({});
  const [failed, setFailed] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    let current = true;
    const load = (name, fetcher, required) =>
      fetcher()
        .then((value) => current && setData((all) => ({ ...all, [name]: value })))
        .catch((problem) => {
          if (!current) return;
          if (required) setError(problem.message);
          else setFailed((all) => ({ ...all, [name]: problem.message }));
        });

    load("guidance", fetchHeatGuidance, true);
    load("report", fetchStationHealth, true);
    load("wbgt", fetchWbgt, false);
    load("forecast", fetchForecast, false);
    return () => {
      current = false;
    };
  }, []);

  return { ...data, failed, error };
}

function tabFromHash() {
  const asked = window.location.hash.slice(1);
  return TABS.some(([key]) => key === asked) ? asked : "guidance";
}

export default function App() {
  const { guidance, report, wbgt, forecast, failed, error } = useJotoData();
  const [tab, setTab] = useState(() => tabFromHash());
  const [workType, setWorkType] = useState("heavy");

  useEffect(() => {
    window.location.hash = tab;
  }, [tab]);

  // Back, forward and a pasted link all change the hash without remounting.
  useEffect(() => {
    const follow = () => setTab(tabFromHash());
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  }, []);

  if (error) {
    return (
      <div className="notice">
        <h1 style={{ fontSize: "1.1rem" }}>Joto Guard is not available</h1>
        <p>{error}</p>
        <code>
          docker compose up --build
          <br />
          {"# or: python -m conduit_sentinel data/raw/organiser --out data/processed"}
          <br />
          {"#     python -m joto_guard wbgt && python -m joto_guard forecast"}
          <br />
          {"#     uvicorn api.app:app --reload"}
        </code>
      </div>
    );
  }

  if (!guidance || !report) {
    return <p className="notice">Loading Joto Guard…</p>;
  }

  const station = report.station;

  return (
    <>
      <header className="page">
        <div className="page-inner">
          <div className="masthead">
            <div>
              <h1>Joto Guard</h1>
              <p>When outdoor work around JKUAT, Juja gets too hot, and how far the station can be trusted.</p>
            </div>
            <dl className="masthead-facts">
              <div>
                <dt>Station</dt>
                <dd>Conduit@Empathy1 · CHORDS 61</dd>
              </div>
              <div>
                <dt>Record</dt>
                <dd>
                  {station.record_start_utc.slice(0, 10)} to {station.record_end_utc.slice(0, 10)}
                </dd>
              </div>
              <div>
                <dt>Health</dt>
                <dd>{report.health.daily.at(-1)?.score ?? "-"} / 100</dd>
              </div>
            </dl>
          </div>

          <nav className="tabs" aria-label="Sections">
            {TABS.map(([key, name]) => (
              <button
                key={key}
                type="button"
                className={key === tab ? "selected" : ""}
                aria-current={key === tab ? "page" : undefined}
                onClick={() => setTab(key)}
              >
                {name}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main>
        {tab === "guidance" ? (
          <>
            <NowCard guidance={guidance} workType={workType} />
            <HeatGuidance guidance={guidance} workType={workType} onWorkType={setWorkType} />
          </>
        ) : null}

        {tab === "forecast" ? (
          <ForecastPanel
            forecast={forecast}
            failure={failed.forecast}
            guidance={guidance}
            workType={workType}
          />
        ) : null}

        {tab === "station" ? (
          <>
            <StationRecord wbgt={wbgt} failure={failed.wbgt} />
            <FirmwareCheck wbgt={wbgt} />
            <Observations
              rain={report.rain}
              light={report.light}
              codes={report.device_codes}
              calibration={wbgt?.light_calibration}
            />
            <StationMap station={station} />
          </>
        ) : null}

        {tab === "health" ? (
          <>
            <StationCard
              station={station}
              generatedAt={report.generated_at_utc}
              version={report.sentinel_version}
            />
            <HealthTrend health={report.health} />
            <CoverageCalendar coverage={report.coverage} />
            <ChannelStatus rows={report.channel_status} rules={report.rules} />
            <Audits audits={report.audits} thermometers={report.thermometer_agreement} />
            <Recommendations items={report.recommendations} />
            <Downloads />
          </>
        ) : null}

        {tab === "method" ? <Method guidance={guidance} /> : null}
      </main>

      <footer className="page">
        <div className="page-inner">
          Joto Guard, built on Conduit Sentinel {report.sentinel_version}. Data attributed to{" "}
          {station.attribution}, CHORDS instrument {station.station_id}. Guidance from NIOSH (2016);
          WBGT after Liljegren et al. (2008).
        </div>
      </footer>
    </>
  );
}
