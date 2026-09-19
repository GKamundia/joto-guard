const STEPS = [
  {
    step: "Ingest",
    uses: "all 26 export columns",
    does: "Three GeoCSV exports become one table: 18,364 observations with 2,825 duplicate timestamps dropped. Units come from the documented schema, not the export header, which mislabels humidity and heat index.",
  },
  {
    step: "Quality control",
    uses: "all 26",
    does: "Sixteen rules flag every value 0 good, 1 suspect, 2 bad, 3 missing: range, step change, flat line, thermometer agreement, gust below wind speed, one rain gauge against the other, empty channels, duplicated export columns, undocumented device codes.",
  },
  {
    step: "Hourly means",
    uses: "flagged observations",
    does: "Built only from good and suspect values, with the count behind each hour. An hour without enough good data stays empty rather than being filled.",
  },
  {
    step: "Light calibration",
    uses: "SI1145 infrared counts",
    does: "Fitted to W/m² against ERA5, allowing for the sensor reading low when the sun is low.",
  },
  {
    step: "WBGT",
    uses: "temperature, humidity, pressure, wind, calibrated solar",
    does: "The Liljegren et al. (2008) heat balance solves globe temperature and natural wet bulb, then combines them into WBGT. No black-globe sensor exists on this station, so the globe is modelled.",
  },
  {
    step: "Audit",
    uses: "the station's own wet bulb, heat index and WBGT",
    does: "Checked against the published formulas. The wet bulb is exactly Stull (2011); the heat index follows the NWS formula; the WBGT matches nothing published and reads 6.1 °C low at midday.",
  },
  {
    step: "Forecast correction",
    uses: "the station's hourly WBGT",
    does: "The station record is the truth an ECMWF forecast is corrected towards, hour of day by hour of day, with a band from the errors on days left out of the fit.",
  },
  {
    step: "Guidance",
    uses: "corrected WBGT and its band",
    does: "NIOSH's limits for four workload categories turn each hour into a level and the minutes of work it allows, separately for workers used to the heat and workers new to it.",
  },
];

const LIMITS = [
  "The record is 19 days of cool season with a six-day hole, and air temperature never passed 28.5 °C. January to March, the hot season, is not in the data at all.",
  "There is no nowcast, because there is no live feed: downloading from the CHORDS portal needs a permission we had not been granted. The service runs on the organisers' exports and forecasts forward.",
  "The light calibration reaches R² 0.67 across daylight but only 0.30 with the sun high, which moves WBGT by about ±1.2 °C at midday. A level near a boundary can be wrong.",
  "WBGT is modelled, not measured: the station has no black-globe thermometer. That is why we recommend one.",
  "The forecast correction is fitted on 15 days, and its band held the station on 78.9 % of hours rather than the 80 % it aims for.",
  "Rain Gauge 2 is a suspected fault from one rainy day, not a confirmed one. The empty battery channel may be an export setting rather than a dead sensor.",
  "No published study has measured heat stress in Juja itself. The worker-heat evidence comes from Mombasa, Tana River and Siaya.",
  "This is guidance to plan work around. It does not replace an employer's duty to watch workers for heat illness.",
];

export default function Method({ guidance }) {
  return (
    <>
      <section className="card">
        <h2>How a reading becomes advice</h2>
        <p className="lead">
          Each step writes files the next one reads. Nothing in the chain invents a number: remove
          the station and there is no WBGT, no correction and no guidance.
        </p>
        <ol className="steps">
          {STEPS.map((item) => (
            <li key={item.step}>
              <h3>{item.step}</h3>
              <p className="uses">{item.uses}</p>
              <p>{item.does}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="card">
        <h2>What this cannot tell you</h2>
        <p className="lead">
          Stated here rather than left to be found. The full list, with the evidence behind each
          one, is in the repository's README and decision records.
        </p>
        <ul className="advice">
          {LIMITS.map((text) => (
            <li key={text.slice(0, 30)}>{text}</li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Sources</h2>
        <ul className="advice">
          {(guidance?.sources ?? []).map((source) => (
            <li key={source}>{source}</li>
          ))}
          <li>
            Station data: Conduit@Empathy1, CHORDS instrument 61, attributed to
            3d-fewsnet.icdp.ucar.edu.
          </li>
          <li>
            Stull, R. (2011). Wet-bulb temperature from relative humidity and air temperature.
            J. Appl. Meteor. Climatol. 50, 2267-2269.
          </li>
        </ul>
      </section>
    </>
  );
}
