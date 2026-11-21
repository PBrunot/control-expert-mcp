# 20261121T114513Z-a78f24bc

Provider/model: `deepseek` / `deepseek-flash`.
Harness base revision: `c10a348e60d82a004f98582048277287c50716d8`; dirty: `False`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Static recognized-subset acceptance; PLC runtime behavior remains unverified.
- API client/model experiment, distinct from ChatGPT UI.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.
- Mutable provider alias: matching model IDs do not guarantee identical weights over time.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| A | alarms | 1 | 1 | 1 | 24.808745499998622 | 50705 |
| A | inspect | 1 | 0 | 0 | 4.799857899997733 | 7742 |
| A | repair | 1 | 1 | 1 | 31.60003180000058 | 85575 |
| A | temperature | 1 | 1 | 1 | 21.23212620000413 | 60008 |
| A | threshold | 1 | 1 | 1 | 19.024000499994145 | 53656 |
| A | overall | 5 | 4 | 4 | 21.23212620000413 | 53656 |
| B | alarms | 1 | 1 | 1 | 26.275027700001374 | 62458 |
| B | inspect | 1 | 0 | 0 | 6.849003200004518 | 9823 |
| B | repair | 1 | 1 | 1 | 16.095335899997735 | 54428 |
| B | temperature | 1 | 1 | 1 | 14.878691099998832 | 36816 |
| B | threshold | 1 | 1 | 1 | 20.719532800001616 | 48581 |
| B | overall | 5 | 4 | 4 | 16.095335899997735 | 48581 |

Original results above remain unchanged. Explicit inspection regrades:


Measured Python source verified against Git (CRLF/LF normalized):

