# 0008. Firmware WBGT: count only large dips below the wet bulb

Date: 19 Sep 2026. Status: accepted.

**Context.** Rule R16 flagged every row where the firmware WBGT was below the firmware wet bulb, and audit A03 called the firmware non-standard when more than 1 % of rows were. Both assumed a real WBGT never falls below the wet bulb. Decision 0007 showed that it can: on a calm, clear night the globe and the wick radiate to a sky colder than the air. The Liljegren model, checked against its original program, puts WBGT below the firmware's wet bulb on 34 % of this station's night hours, by at most 0.76 °C. In still air between 8 and 25 °C, its lowest is 1.4 °C below. So "below at all" flags normal nights, and a share test on it cannot tell a standard formula from a wrong one.

**Decision.** R16 and A03 count a row only when the firmware WBGT is more than 1.5 °C below the firmware wet bulb. That is just beyond the model's still-air limit here. The margin is `qc.wbgt_below_wet_bulb_margin_c` in `config/qc_rules.yaml`. A03 still reports the share below at all, for context, and its verdict rests on the share more than 1.5 °C below. Spec version 0.4 carries the change.

**Effect on the organiser exports.**

| | Before | After |
|---|---|---|
| Acceptance files (11,302 rows) | 51.6 % below; night 71.3 %, day 34.9 % | 34.1 % more than 1.5 °C below; night 51.3 %, day 19.5 % |
| All three files (18,364 rows) | 57.3 % below | 38.6 % more than 1.5 °C below |
| A03 verdict | non-standard | non-standard |

The firmware finding stands; it now rests on dips a standard WBGT does not produce. R16 flags fewer rows as suspect. The health score is unaffected, because the `derived_fw` group is not scored.

**Consequences.** The expected A03 values in spec section 11 and the acceptance tests change. The margin is specific to this station's climate: a colder or calmer site could need a larger one, and the model can recompute it.
