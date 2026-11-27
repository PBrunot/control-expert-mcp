# 20261121T100834Z-be7edc84

Provider/model: `deepseek` / `deepseek-flash`.
Harness base revision: `dd3c8757b38dafb9eedbac11428ef42ae834ea9c`; dirty: `True`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Static recognized-subset acceptance; PLC runtime behavior remains unverified.
- API client/model experiment, distinct from ChatGPT UI.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.
- Mutable provider alias: matching model IDs do not guarantee identical weights over time.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| A | inspect | 1 | 0 | 0 | 6.5539921000017785 | 12697 |
| A | repair | 1 | 1 | 1 | 23.012446500004444 | 66946 |
| A | temperature | 1 | 1 | 1 | 17.748672200003057 | 56882 |
| A | threshold | 1 | 1 | 1 | 19.87760949999938 | 59375 |
| A | overall | 4 | 3 | 3 | 18.81314085000122 | 58128.5 |
| B | inspect | 1 | 0 | 0 | 6.4457602000038605 | 9596 |
| B | repair | 1 | 1 | 1 | 36.07084639999812 | 92159 |
| B | temperature | 1 | 1 | 1 | 19.918886599996767 | 60749 |
| B | threshold | 1 | 1 | 1 | 21.041752599994652 | 66856 |
| B | overall | 4 | 3 | 3 | 20.48031959999571 | 63802.5 |

Original results above remain unchanged. Explicit inspection regrades:

- `feeder-3`, A: 4/4 accepted.
- `feeder-3`, B: 4/4 accepted.

Measured Python source verified against Git (CRLF/LF normalized):

- A: `d94539a9068ae11474460caeb9c3224462138d7f` (original dirty-state metadata retained).
- B: `d94539a9068ae11474460caeb9c3224462138d7f` (original dirty-state metadata retained).
