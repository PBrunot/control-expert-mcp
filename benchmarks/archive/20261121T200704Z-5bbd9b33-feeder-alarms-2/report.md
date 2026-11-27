# 20261121T200704Z-5bbd9b33

Provider/model: `deepseek` / `deepseek-flash`.
Harness base revision: `0b53d53d8b5e4713ddb97e473a14cf5208499203`; dirty: `True`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Static recognized-subset acceptance; PLC runtime behavior remains unverified.
- API client/model experiment, distinct from ChatGPT UI.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.
- Mutable provider alias: matching model IDs do not guarantee identical weights over time.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| A | alarms | 1 | 1 | 1 | 25.908167699999467 | 58049 |
| A | inspect | 1 | 1 | 0 | 31.08523530000093 | 48709 |
| A | io_mapping | 1 | 0 | 0 | 88.78584889999911 | 2159675 |
| A | repair | 1 | 1 | 1 | 34.25332479999997 | 77814 |
| A | temperature | 1 | 1 | 1 | 18.516890500002773 | 51629 |
| A | threshold | 1 | 1 | 1 | 14.273850000001403 | 52896 |
| A | weighing | 1 | 1 | 0 | 52.20488679999835 | 110953 |
| A | overall | 7 | 6 | 4 | 31.08523530000093 | 58049 |
| B | alarms | 1 | 1 | 1 | 26.90035180000268 | 81938 |
| B | inspect | 1 | 1 | 0 | 19.448521599999367 | 42846 |
| B | io_mapping | 1 | 0 | 0 | 60.9517878000006 | 1031875 |
| B | repair | 1 | 1 | 1 | 20.473704899999575 | 74175 |
| B | temperature | 1 | 1 | 1 | 15.642504199997347 | 46232 |
| B | threshold | 1 | 1 | 1 | 17.396494299999176 | 51978 |
| B | weighing | 1 | 1 | 0 | 66.72628089999853 | 176807 |
| B | overall | 7 | 6 | 4 | 20.473704899999575 | 74175 |

Original results above remain unchanged. Explicit inspection regrades:

- `feeder-alarms-2`, A: 6/7 accepted.
- `feeder-alarms-2`, B: 6/7 accepted.

Measured Python source verified against Git (CRLF/LF normalized):

