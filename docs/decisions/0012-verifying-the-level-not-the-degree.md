# 0012. Verifying the level, not the degree

Date: 19 Sep 2026. Status: accepted.

**Context.** Decision 0010 scored the forecast correction in degrees: mean absolute error 1.07 °C
on days left out of its fit, against 1.46 °C raw and 1.38 °C for the station's own average at that
hour. Nobody had asked the question a supervisor actually asks, which is whether the level the
forecast implies is the level the station turned out to justify. A 1 °C error matters enormously
next to a limit and not at all in the middle of a band.

**What the data showed.** `python -m joto_guard verify` scores the corrected forecast against the
station on 1,244 hourly pairs over 15 days, each day left out of the fit, for forecasts made 0 to
3 days ahead.

| Work type | Level exactly right | Said it was safer than it was | Said it was worse |
|---|---|---|---|
| Light | 94.8 % | 4.6 % | 0.6 % |
| Moderate | 89.2 % | 7.9 % | 2.9 % |
| Heavy | 86.3 % | 7.3 % | 6.4 % |
| Very heavy | 84.4 % | 8.4 % | 7.2 % |

The two errors are not equal. Saying an hour is worse than it turned out costs work. Saying it is
safer than it turned out is the one that can hurt somebody, and for heavy work it happens on about
one hour in fourteen. For moderate and very heavy work it can be wrong by two levels, not one.

Three other things the degrees alone had hidden:

- **The correction fixes the average, not the tail.** Bias falls to zero and mean absolute error to
  1.07 °C, but the 90th percentile error is still 2.50 °C and the worst is 6.83 °C, slightly worse
  than the raw forecast's worst of 6.44 °C.
- **The error is concentrated where the decision is made.** Mean absolute error runs 0.4 to 0.9 °C
  from 17:00 to 07:00 and 1.5 to 2.2 °C from 08:00 to 16:00, peaking at 2.2 °C at 08:00. That is
  the morning ramp, when a supervisor is planning the day, and it matches the light calibration's
  weakness at high sun (decision 0006).
- **Skill decays gently with lead time**: 0.98 °C same day, 1.02, 1.14 and 1.16 °C at one, two and
  three days ahead. All four beat the 1.38 °C baseline.

**Decision.** Keep the central corrected value as the level shown, and publish the under-warning
rate beside it rather than only the error in degrees. Record the alternative, because it is a real
choice the team may revisit: taking the band's upper edge as the warning instead cuts under-warning
to 0.2 % for heavy work, but raises over-warning from 6.4 % to 20.3 %.

We did not take it, for two reasons. Over-warning one hour in five teaches people to ignore the
service, which is its own safety failure. And the band's upper edge is already in the product as
the "could reach the next level" marker, so a supervisor planning conservatively can see it
without everyone else being told to stop work that was fine.

**Consequences.**

- `python -m joto_guard verify --past-forecasts <file>` writes `data/processed/verification.json`
  and prints the table above. It is not part of the regular pipeline; run it when the correction is
  refitted.
- The README states the under-warning rate, not only the mean absolute error.
- This should be run again on a longer record. Fifteen cool-season days is a thin basis, and only
  26 % of the heavy-work hours in it were above normal at all, so the level agreement is dominated
  by hours that were comfortably normal.
