# 20261127T185620Z-558a4028

Provider/model: `claude-code` / `claude-haiku-4-5-20251001`.
Harness base revision: `8432871bba754e95819570a1addd000608242dce`; dirty: `True`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Static recognized-subset acceptance; PLC runtime behavior remains unverified.
- Claude Code CLI agent loop (subscription login, built-in tools disabled, server instructions as replacement system prompt); distinct from interactive Claude Code defaults.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| A | alarms | 1 | 0 | 1 | 40.66143179999199 | 65193 |
| A | inspect | 1 | 0 | 0 | 19.667896899976768 | 16072 |
| A | io_mapping | 1 | 1 | 0 | 97.78541759995278 | 203236 |
| A | repair | 1 | 0 | 1 | 154.87764229997993 | 401734 |
| A | temperature | 1 | 1 | 1 | 26.222108499961905 | 42928 |
| A | threshold | 1 | 1 | 1 | 31.861743599991314 | 46278 |
| A | weighing | 1 | 1 | 0 | 39.5384571000468 | 48724 |
| A | overall | 7 | 4 | 4 | 39.5384571000468 | 48724 |
| B | alarms | 1 | 0 | 1 | 53.52888870006427 | 96339 |
| B | inspect | 1 | 0 | 0 | 21.368805999984033 | 17736 |
| B | io_mapping | 1 | 1 | 0 | 128.08830780000426 | 222298 |
| B | repair | 1 | 0 | 1 | 84.23748780007008 | 114933 |
| B | temperature | 1 | 1 | 1 | 28.95216560002882 | 48308 |
| B | threshold | 1 | 1 | 1 | 28.594349000020884 | 48474 |
| B | weighing | 1 | 1 | 0 | 44.17387759999838 | 55924 |
| B | overall | 7 | 4 | 4 | 44.17387759999838 | 55924 |

Original results above remain unchanged. Explicit inspection regrades:

- `demo-io-mapping-6`, A: 4/7 accepted.
- `demo-io-mapping-6`, B: 4/7 accepted.
- `feeder-3`, A: 5/7 accepted.
- `feeder-3`, B: 5/7 accepted.
- `feeder-alarms-2`, A: 5/7 accepted.
- `feeder-alarms-2`, B: 5/7 accepted.

Measured Python source verified against Git (CRLF/LF normalized):

