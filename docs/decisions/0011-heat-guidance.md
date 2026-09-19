# 0011. Heat guidance by type of work, from NIOSH limits

Date: 19 Sep 2026. Status: accepted.

**Context.** Joto Guard turns WBGT into advice, which needs published limits that depend on how hard people work. We found no Kenyan regulation that sets WBGT limits. The international standard, ISO 7243:2017, sets limits by metabolic rate for acclimatized and unacclimatized workers, but it is not freely available. The US National Institute for Occupational Safety and Health (NIOSH) publishes the same kind of limits as equations, in a public-domain document [1]. OSHA's technical manual directs users to the Liljegren WBGT model, which Joto Guard uses, when no WBGT meter is available [2].

**Decision.** All values live in `config/heat_guidance.yaml`, with the page each comes from; `src/joto_guard/bands.py` applies them.

- **Two limits.** For a metabolic rate M in watts, with WBGT and M both averaged over an hour (NIOSH section 1.1.3, page 4; section 8.1, page 93):
  - acclimatized workers (the REL): 56.7 − 11.5 log10 M;
  - workers not yet acclimatized to heat (the RAL): 59.9 − 14.1 log10 M.
- **Four types of work.** These are NIOSH's categories from Table 5-1 (page 70), each taken at the top of its range so the limit protects everyone in it:

  | Work | Up to | Acclimatized limit | New-worker limit | Examples [3] |
  |---|---|---|---|---|
  | Light | 233 W | 29.5 °C | 26.5 °C | masonry or concrete work, light effort; light farm work |
  | Moderate | 349 W | 27.5 °C | 24.1 °C | picking fruit; rice planting; walking with light loads |
  | Heavy | 465 W | 26.0 °C | 22.3 °C | masonry or concrete work, moderate effort; harvesting crops; shovelling, moderate effort; carrying 23 to 34 kg |
  | Very heavy | 580 W | 24.9 °C | 20.9 °C | shovelling, vigorous effort; carrying 34 to 45 kg |

  The examples come from the Compendium of Physical Activities, which NIOSH points to for the metabolic rate of a task (page 4). Its MET values convert to watts for NIOSH's 70 kg reference worker as W = MET × 81.4.
- **Work/rest.** NIOSH averages metabolic heat over the hour, rest included, so resting part of the hour lowers the average and raises the allowed WBGT.
  - For each hour, the guidance finds the longest spell of work that keeps the hourly average within the limit. The spells tried are 60, 45, 30 or 15 minutes, as in NIOSH Figures 8-1 and 8-2 (page 94).
  - Rest is taken at 117 W (Table 5-1) and, conservatively, in the same heat.
- **Four levels.**
  - `normal`: continuous work is within the limit for new workers too.
  - `acclimatized_only`: only acclimatized workers can work continuously; new workers follow NIOSH's acclimatization plan (Table 4-1, page 34).
  - `work_rest`: acclimatized workers need a work/rest schedule.
  - `reschedule`: even 15 minutes of work an hour exceeds the limit.
- **Uncertainty.** Each forecast hour also reports the level at the top of the forecast's uncertainty band (decision 0010), so the guidance can say when an hour *might* reach a level.
- **Advice.** Water: about a cup (240 mL) every 15 to 20 minutes (executive summary, page vii). Rest in the shade (Table 8-1 note, page 104).

**Not used.**

- **NIOSH Table 8-1's work/rest table (from the US Department of Defense).** Its "easy", "moderate" and "hard" work are 250, 425 and 600 W. Its "moderate" is NIOSH's "heavy", so mixing the two would put the same shovelling in different rows.
- **The ACGIH threshold limit values.** They are copyrighted and not publicly available [2].
- **NIOSH's worked example** (page 4) quotes 27.8 °C and 25 °C for 300 kcal/h, read from its figures. The equations give 27.5 °C and 24.0 °C, and we use the equations.

**What it shows on the station record.** Over the 11 full days from 28 August to 15 September 2026, with no hour needing rescheduling:

| Work | Hours only acclimatized workers could work through | Hours needing work/rest |
|---|---|---|
| Light | 21, on 6 days | none |
| Moderate | 45, on 9 days | 4, on 3 days |
| Heavy | 40, on 9 days | 24, on 6 days |
| Very heavy | 42, on 11 days | 37, on 9 days |

- **Heavy work.** On six days, acclimatized workers doing heavy work needed breaks, from as early as 09:00 until 16:00 at the latest. The hottest day was 14 September: six hours, peaking at 28.5 °C WBGT. In most of those hours 45 minutes of work per hour stayed within the limit, in nine it was 30 minutes, and in one it was 15.
- **New workers.** They reached their limit for moderate work on nine of the eleven days.

**Limits.**

- NIOSH's limits are for healthy workers in conventional one-layer work clothing (chapter 1). Heavier clothing and personal risk factors, such as some medicines, call for more protection (chapters 1, 4 and 7).
- The categories describe the average effort over an hour, not the hardest minute.
- The station's WBGT carries about ±1–2 °C of uncertainty at midday (decision 0007), and the forecast has its own band (decision 0010). The record covers only the cool season.
- This is guidance to plan work around. It does not replace an employer's duty to watch workers for heat illness.

**Consequences.**

- `python -m joto_guard forecast` writes `data/processed/heat_guidance.json`, with the level and allowed work minutes for every forecast hour and work type and a summary for each day. The API and the Telegram bot read that file.

**References.**

1. NIOSH (2016). *Criteria for a Recommended Standard: Occupational Exposure to Heat and Hot Environments.* DHHS (NIOSH) Publication No. 2016-106. https://www.cdc.gov/niosh/docs/2016-106/pdfs/2016-106.pdf
2. OSHA Technical Manual, Section III, Chapter 4: Heat Stress. https://www.osha.gov/otm/section-3-health-hazards/chapter-4
3. Herrmann, S. D. et al. (2024). 2024 Adult Compendium of Physical Activities: a third update of the energy costs of human activities. *Journal of Sport and Health Science* 13, 6–12. https://doi.org/10.1016/j.jshs.2023.10.010. Activity codes 11146, 11147, 11195, 11480, 11482, 11510, 11560, 11570, 11795, 11830 and 11840 (https://pacompendium.com/occupation/).
