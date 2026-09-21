# 0013. The whole year, not just the weeks on record

Date: 21 Sep 2026. Status: accepted.

**Context.** The station record is three cool-season weeks, 28 August to 15 September 2026,
and air temperature never passed 28.5 °C in it. On its own it makes Juja look like a mild
place to work. That is the obvious question any reader would ask of a heat warning for
Juja, and the record cannot answer it, because January to March is not in it.

**Decision.** Reconstruct every working hour since 2016 from ERA5 reanalysis at the
station's grid cell, through the same WBGT model everything else uses
(`joto_guard.forecast.forecast_wbgt`, since ERA5 comes in the same variables as the
forecast). Count the share of working hours, 07:00 to 18:00 local, over each NIOSH limit,
by month.

ERA5 reads cool against the station. Over the 311 hours they share, its WBGT is 2.1 °C
lower during working hours, and lower in 85 % of them. So two figures are given:

- **at least**: raw ERA5. It reads cool, so the true share is higher. No assumptions.
- **likely**: ERA5 corrected towards the station by local hour, the method decision 0010
  uses for the forecast.

**What it shows.** Heavy work, 2016 to 2026, likely figure:

| | January to March | August to September |
|---|---|---|
| Needs breaks even for workers used to the heat (over 26.0 °C) | 43 % of working hours | 17 % |
| Over the limit for new workers (22.3 °C) | 80 % | 61 % |

March and April are the worst months, at about half of all working hours needing breaks for
workers used to the heat; July is the mildest at 8 %.

**Checked against the station.** The reconstruction's August and September figures should
look like what the station itself recorded in those months, and they do. Heavy work over
the new-worker limit: 61 % reconstructed, 57 % recorded by the station over its 143 working
hours. The other work types agree within a few points too.

**Consequences.**

- The Guidance tab now ends with the whole year for the chosen type of work, and says
  which figure is which.
- The result is tracked in `config/hot_season.json` rather than regenerated on each run,
  like the calibration and the correction: the fetch is 11 years of hourly data, and a
  rerun should not silently change a number the README quotes.
- **The correction was measured in the cool season.** Applying it to the hot season assumes
  ERA5 errs by hour of day the same way year round, which one station and three weeks
  cannot test. That is why the uncorrected floor is shown beside it, not hidden.
- Heavy work over the acclimatized limit is 5 % on the floor and 43 % likely. The gap is
  large because that limit sits near the top of the distribution, where 2 °C moves many
  hours across it. The station's own record favours the likely figure.
