# 20261123T205344Z-37142f78

Provider/model: `deepseek` / `deepseek-flash`.
Harness base revision: `a28ec8a8e9609d62bbd44d1944155deb0df20558`; dirty: `True`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Static recognized-subset acceptance; PLC runtime behavior remains unverified.
- API client/model experiment, distinct from ChatGPT UI.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.
- Mutable provider alias: matching model IDs do not guarantee identical weights over time.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| A | inspect | 1 | 1 | 0 | 9.645760500017786 | 19007 |
| A | repair | 1 | 1 | 1 | 20.62003150000237 | 70446 |
| A | weighing | 1 | 1 | 0 | 88.18700810000882 | 159450 |
| A | overall | 3 | 3 | 1 | 20.62003150000237 | 70446 |
| B | inspect | 1 | 1 | 0 | 23.032105899997987 | 109474 |
| B | weighing | 1 | 1 | 0 | 54.65536529998644 | 87006 |
| B | overall | 2 | 2 | 0 | 38.843735599992215 | 98240.0 |

Original results above remain unchanged. Explicit inspection regrades:

- `feeder-3`, A: 3/3 accepted.
- `feeder-3`, B: 2/2 accepted.

Measured Python source verified against Git (CRLF/LF normalized):

