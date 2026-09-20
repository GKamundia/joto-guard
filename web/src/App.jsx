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
import { shortDay } from "./format";

const TABS = [
  ["guidance", "Guidance"],
  ["forecast", "Forecast"],
  ["station", "Station record"],
  ["health", "Station health"],
  ["method", "Method"],
];

const THEME_KEY = "joto-theme";

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

/** Storage is unavailable in some private-browsing modes; the page still has to render. */
function remember(key, value) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // The choice then lasts for this visit only.
  }
}

function storedTheme() {
  try {
    return window.localStorage.getItem(THEME_KEY) ?? "system";
  } catch {
    return "system";
  }
}

function prefersDark() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

function useTheme() {
  const [theme, setTheme] = useState(storedTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") {
      delete root.dataset.theme;
      remember(THEME_KEY, null);
    } else {
      root.dataset.theme = theme;
      remember(THEME_KEY, theme);
    }
  }, [theme]);

  const dark = theme === "dark" || (theme === "system" && prefersDark());
  return [dark, () => setTheme(dark ? "light" : "dark")];
}

function tabFromHash() {
  const asked = window.location.hash.slice(1);
  return TABS.some(([key]) => key === asked) ? asked : "guidance";
}

function ThemeButton({ dark, onToggle }) {
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={onToggle}
      title={dark ? "Switch to the light theme" : "Switch to the dark theme"}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        {dark ? (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
          </>
        ) : (
          <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" />
        )}
      </svg>
      {dark ? "Light" : "Dark"}
    </button>
  );
}

function LoadingPage() {
  return (
    <main aria-busy="true">
      <p className="sr-only">Loading Joto Guard</p>
      <section className="card">
        <div className="skeleton">
          <span className="third" />
          <span className="tall" />
          <span className="half" />
        </div>
      </section>
      <section className="card">
        <div className="skeleton">
          <span className="half" />
          <span />
          <span className="tall" />
        </div>
      </section>
    </main>
  );
}

export default function App() {
  const { guidance, report, wbgt, forecast, failed, error } = useJotoData();
  const [dark, toggleTheme] = useTheme();
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
        <h1>Joto Guard is not available</h1>
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
    return <LoadingPage />;
  }

  const station = report.station;
  const score = report.health.daily.at(-1)?.score;

  return (
    <>
      <header className="page">
        <div className="page-inner">
          <div className="masthead">
            <div className="brand">
              <span className="brand-mark" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="9" r="4" />
                  <path d="M12 1v2M4.9 4.9l1.4 1.4M1 9h2M21 9h2M19.1 4.9l-1.4 1.4M3 17h7M14 17h7M6 21h5M15 21h3" />
                </svg>
              </span>
              <h1>
                Joto Guard
                <span>
                  When outdoor work around JKUAT, Juja gets too hot, and how far the station can be
                  trusted.
                </span>
              </h1>
            </div>

            <div className="masthead-side">
              <dl className="masthead-facts">
                <div>
                  <dt>Station</dt>
                  <dd>Conduit@Empathy1 · CHORDS 61</dd>
                </div>
                <div>
                  <dt>Record</dt>
                  <dd>
                    {shortDay(station.record_start_utc)} – {shortDay(station.record_end_utc)}
                  </dd>
                </div>
                <div>
                  <dt>Health</dt>
                  <dd>{score ?? "-"} / 100</dd>
                </div>
              </dl>
              <ThemeButton dark={dark} onToggle={toggleTheme} />
            </div>
          </div>
        </div>
      </header>

      <nav className="tabs-bar" aria-label="Sections">
        <div className="page-inner">
          <div className="tabs">
            {TABS.map(([key, name]) => (
              <button
                key={key}
                type="button"
                aria-current={key === tab ? "page" : undefined}
                className={key === tab ? "selected" : ""}
                onClick={() => setTab(key)}
              >
                {name}
              </button>
            ))}
          </div>
        </div>
      </nav>

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
