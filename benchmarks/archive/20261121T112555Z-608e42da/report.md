# 20261121T112555Z-608e42da

Provider/model: `openai` / `gpt-5.5-2026-04-23`.
Harness base revision: `2cb614de3a26e9c75bdafaade2897fd664d805e0`; dirty: `True`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Static recognized-subset acceptance; PLC runtime behavior remains unverified.
- API client/model experiment, distinct from ChatGPT UI.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| A | alarms | 1 | 1 | 1 | 31.642021999999997 | 37811 |
| A | inspect | 1 | 1 | 0 | 12.531379399995785 | 7556 |
| A | repair | 1 | 1 | 1 | 21.0291353000066 | 38759 |
| A | temperature | 1 | 1 | 1 | 19.923335899999074 | 25254 |
| A | threshold | 1 | 0 | 1 | 11.132631400003447 | None |
| A | overall | 5 | 4 | 4 | 19.923335899999074 | 31532.5 |
| B | alarms | 1 | 1 | 1 | 30.00257870000496 | 30593 |
| B | inspect | 1 | 1 | 0 | 11.242602799997258 | 9129 |
| B | repair | 1 | 1 | 1 | 22.652234100001806 | 42720 |
| B | temperature | 1 | 1 | 1 | 21.753046700003324 | 27855 |
| B | threshold | 1 | 1 | 1 | 19.955414099997142 | 28406 |
| B | overall | 5 | 5 | 4 | 21.753046700003324 | 28406 |

Original results above remain unchanged. Explicit inspection regrades:


Measured Python source verified against Git (CRLF/LF normalized):

