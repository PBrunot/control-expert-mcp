# 20261121T204037Z-e4c05842

Provider/model: `openai` / `gpt-5.5-2026-04-23`.
Harness base revision: `c17ace01f2bd8fb5724812c436e631aa680d5141`; dirty: `False`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Static recognized-subset acceptance; PLC runtime behavior remains unverified.
- API client/model experiment, distinct from ChatGPT UI.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| A | alarms | 1 | 0 | 1 | 0.7587691000007908 | None |
| A | io_mapping | 1 | 0 | 0 | 104.71821269999782 | 895668 |
| A | temperature | 1 | 1 | 1 | 20.630502799998794 | 26665 |
| A | threshold | 1 | 1 | 1 | 21.74815529999978 | 23513 |
| A | overall | 4 | 2 | 3 | 21.189329049999287 | 26665 |
| B | io_mapping | 1 | 0 | 0 | 79.22939300000144 | 791367 |
| B | temperature | 1 | 1 | 1 | 20.302485700001853 | 29200 |
| B | threshold | 1 | 1 | 1 | 24.14046629999939 | 25585 |
| B | overall | 3 | 2 | 2 | 24.14046629999939 | 29200 |

Original results above remain unchanged. Explicit inspection regrades:

- `demo-io-mapping-2`, A: 2/4 accepted.
- `demo-io-mapping-2`, B: 2/3 accepted.
- `demo-io-mapping-3`, A: 2/4 accepted.
- `demo-io-mapping-3`, B: 3/3 accepted.

Measured Python source verified against Git (CRLF/LF normalized):

