import { useEffect, useState } from "react";
import { fetchHeatGuidance, fetchStationHealth, fetchWbgt } from "./api";
import Audits from "./components/Audits";
import ChannelStatus from "./components/ChannelStatus";
import CoverageCalendar from "./components/CoverageCalendar";
import Downloads from "./components/Downloads";
import FirmwareCheck from "./components/FirmwareCheck";
import HealthTrend from "./components/HealthTrend";
import HeatGuidance from "./components/HeatGuidance";
import Observations from "./components/Observations";
import Recommendations from "./components/Recommendations";
import StationCard from "./components/StationCard";
import StationMap from "./components/StationMap";

export default function App() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [guidance, setGuidance] = useState(null);
  const [guidanceError, setGuidanceError] = useState(null);
  const [wbgt, setWbgt] = useState(null);

  useEffect(() => {
    let current = true;
    fetchStationHealth()
      .then((data) => current && setReport(data))
      .catch((problem) => current && setError(problem.message));
    fetchHeatGuidance()
      .then((data) => current && setGuidance(data))
      .catch((problem) => current && setGuidanceError(problem.message));
    fetchWbgt()
      .then((data) => current && setWbgt(data))
      .catch(() => {});
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
        <h1>Joto Guard</h1>
        <p>
          When outdoor work around JKUAT, Juja, gets too hot, from the Conduit@Empathy1 weather
          station, and how far that station can be trusted.
        </p>
      </header>

      <main>
        <HeatGuidance guidance={guidance} error={guidanceError} />
        <h2 className="part">Station Health Report</h2>
        <StationCard
          station={report.station}
          generatedAt={report.generated_at_utc}
          version={report.sentinel_version}
        />
        <HealthTrend health={report.health} />
        <CoverageCalendar coverage={report.coverage} />
        <ChannelStatus rows={report.channel_status} rules={report.rules} />
        <Audits audits={report.audits} thermometers={report.thermometer_agreement} />
        <FirmwareCheck wbgt={wbgt} />
        <Observations
          rain={report.rain}
          light={report.light}
          codes={report.device_codes}
          calibration={wbgt?.light_calibration}
        />
        <Recommendations items={report.recommendations} />
        <StationMap station={report.station} />
        <Downloads />
      </main>

      <footer className="page">
        Joto Guard, built on Conduit Sentinel {report.sentinel_version}. Data attributed to{" "}
        {report.station.attribution}, CHORDS instrument {report.station.station_id}.
      </footer>
    </>
  );
}
