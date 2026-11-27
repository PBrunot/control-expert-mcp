# 20261121T211320Z-ec8c65a1

Provider/model: `openai` / `gpt-6-luna`.
Harness base revision: `c17ace01f2bd8fb5724812c436e631aa680d5141`; dirty: `True`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Static recognized-subset acceptance; PLC runtime behavior remains unverified.
- API client/model experiment, distinct from ChatGPT UI.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.
- Mutable provider alias: matching model IDs do not guarantee identical weights over time.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| A | alarms | 1 | 1 | 1 | 15.31014850000065 | 36344 |
| A | inspect | 1 | 1 | 0 | 9.136505000002217 | 14413 |
| A | io_mapping | 1 | 0 | 0 | 44.97436540000126 | 471142 |
| A | repair | 1 | 1 | 1 | 16.261517499999172 | 49168 |
| A | temperature | 1 | 1 | 1 | 12.210270699997636 | 25572 |
| A | threshold | 1 | 1 | 1 | 14.782833199999004 | 34699 |
| A | weighing | 1 | 1 | 0 | 33.81924980000258 | 86278 |
| A | overall | 7 | 6 | 4 | 15.31014850000065 | 36344 |
| B | alarms | 1 | 1 | 1 | 16.763072399997327 | 47338 |
| B | inspect | 1 | 1 | 0 | 21.496930999997858 | 111914 |
| B | io_mapping | 1 | 0 | 0 | 57.88744980000047 | 340815 |
| B | repair | 1 | 1 | 1 | 12.966658599998482 | 35383 |
| B | temperature | 1 | 1 | 1 | 14.198835499999404 | 37751 |
| B | threshold | 1 | 1 | 1 | 14.777804999997898 | 28459 |
| B | weighing | 1 | 1 | 0 | 41.42795169999954 | 126967 |
| B | overall | 7 | 6 | 4 | 16.763072399997327 | 47338 |

Original results above remain unchanged. Explicit inspection regrades:

- `feeder-alarms-2`, A: 6/7 accepted.
- `feeder-alarms-2`, B: 6/7 accepted.

Measured Python source verified against Git (CRLF/LF normalized):

