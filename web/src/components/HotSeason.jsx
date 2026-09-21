import { number } from "../format";

const WORK_NAMES = {
  light: "Light work",
  moderate: "Moderate work",
  heavy: "Heavy work",
  very_heavy: "Very heavy work",
};

/** "Jan to Mar", not "Jan to Feb to Mar". */
const span = (names) => (names.length > 1 ? `${names[0]} to ${names.at(-1)}` : names[0]);

/**
 * The station's own record is three cool-season weeks, and a reader who only saw that would
 * fairly ask why Juja needs a heat warning at all. This answers with the months the record
 * does not cover: every working hour since 2016, from reanalysis corrected towards the
 * station.
 */
export default function HotSeason({ season, workType }) {
  if (!season) return null;

  const likely = season.hot_season.likely[workType];
  const floor = season.hot_season.at_least[workType];
  const record = season.record_season.likely[workType];
  const limits = season.limits[workType];
  const months = season.by_month;

  return (
    <section className="card hot-season">
      <h2>It is not this mild all year</h2>
      <p className="lead">
        The station's record is three cool-season weeks. For the rest of the year this uses every
        working hour ({season.working_hours}) from {season.years[0]} to {season.years[1]}: ERA5
        reanalysis, run through the same WBGT model and corrected towards the station, which it
        reads {number(-season.reanalysis_minus_station_c, 1)} °C cooler than.
      </p>

      <div className="season-compare">
        <div>
          <p className="label">
            {span(season.hot_months)}, {WORK_NAMES[workType].toLowerCase()}
          </p>
          <p className="big">{number(likely.over_acclimatized_pct, 0)} %</p>
          <p className="label">
            of working hours need breaks even for workers used to the heat (over{" "}
            {number(limits.acclimatized_c, 1)} °C)
          </p>
        </div>
        <div>
          <p className="label">New workers, same months</p>
          <p className="big">{number(likely.over_new_workers_pct, 0)} %</p>
          <p className="label">of working hours over their limit of {number(limits.new_workers_c, 1)} °C</p>
        </div>
        <div className="muted">
          <p className="label">{span(season.record_months)}, the months on record</p>
          <p className="big">{number(record.over_acclimatized_pct, 0)} %</p>
          <p className="label">need breaks for workers used to the heat</p>
        </div>
      </div>

      <div className="season-bars" role="img" aria-label="Share of working hours over the new-worker limit, by month">
        {months.map((month) => {
          const share = month.likely[workType].over_new_workers_pct;
          const hard = month.likely[workType].over_acclimatized_pct;
          return (
            <div key={month.month} className="season-bar">
              <div className="season-track">
                <div
                  className="season-fill"
                  style={{ height: `${share}%` }}
                  title={`${month.name}: ${number(share, 0)} % of working hours over the new-worker limit, ${number(hard, 0)} % over the limit for workers used to the heat`}
                >
                  <div className="season-hard" style={{ height: `${share ? (hard / share) * 100 : 0}%` }} />
                </div>
              </div>
              <span>{month.name}</span>
            </div>
          );
        })}
      </div>
      <p className="season-key">
        <span className="key-new" /> over the new-worker limit <span className="key-hard" /> over
        the limit for workers used to the heat too
      </p>

      <p className="lead" style={{ marginBottom: 0 }}>
        These are the likely figures. Raw reanalysis, which reads cool, puts the hot season at no
        less than {number(floor.over_new_workers_pct, 0)} % over the new-worker limit and{" "}
        {number(floor.over_acclimatized_pct, 0)} % over the other: a floor, not an estimate. The
        correction was measured in the cool season, and applied to the hot one it is an assumption.
      </p>
    </section>
  );
}
