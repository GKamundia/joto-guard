import { useEffect, useState } from "react";
import { fetchStationHealth } from "./api";
import Audits from "./components/Audits";
import ChannelStatus from "./components/ChannelStatus";
import CoverageCalendar from "./components/CoverageCalendar";
import Downloads from "./components/Downloads";
import HealthTrend from "./components/HealthTrend";
import Observations from "./components/Observations";
import Recommendations from "./components/Recommendations";
import StationCard from "./components/StationCard";
import StationMap from "./components/StationMap";

export default function App() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let current = true;
    fetchStationHealth()
      .then((data) => current && setReport(data))
      .catch((problem) => current && setError(problem.message));
    return () => {
      current = false;
    };
  }, []);

  if (error) {
    return (
      <div className="notice">
        <h1 style={{ fontSize: "1.1rem" }}>The report is not available</h1>
        <p>{error}</p>
        <code>
          python -m conduit_sentinel data/raw/organiser --out data/processed
          <br />
          uvicorn api.app:app --reload
        </code>
      </div>
    );
  }

  if (!report) {
    return <p className="notice">Loading the Station Health Report…</p>;
  }

  return (
    <>
      <header className="page">
        <h1>Station Health Report</h1>
        <p>
          How far the Conduit@Empathy1 weather station can be trusted, and what to fix. Every
          figure comes from the station's own records.
        </p>
      </header>

      <main>
        <StationCard
          station={report.station}
          generatedAt={report.generated_at_utc}
          version={report.sentinel_version}
        />
        <HealthTrend health={report.health} />
        <CoverageCalendar coverage={report.coverage} />
        <ChannelStatus rows={report.channel_status} rules={report.rules} />
        <Audits audits={report.audits} thermometers={report.thermometer_agreement} />
        <Observations rain={report.rain} light={report.light} codes={report.device_codes} />
        <Recommendations items={report.recommendations} />
        <StationMap station={report.station} />
        <Downloads />
      </main>

      <footer className="page">
        Conduit Sentinel {report.sentinel_version}. Data attributed to{" "}
        {report.station.attribution}, CHORDS instrument {report.station.station_id}.
      </footer>
    </>
  );
}
