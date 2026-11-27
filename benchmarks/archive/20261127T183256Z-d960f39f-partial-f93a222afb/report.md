# 20261127T183256Z-d960f39f

Provider/model: `claude-code` / `claude-haiku-4-5-20251001`.
Harness base revision: `8432871bba754e95819570a1addd000608242dce`; dirty: `True`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Static recognized-subset acceptance; PLC runtime behavior remains unverified.
- Claude Code CLI agent loop (subscription login, built-in tools disabled, server instructions as replacement system prompt); distinct from interactive Claude Code defaults.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| A | alarms | 1 | 0 | 1 | 53.168614299967885 | 86856 |
| A | io_mapping | 1 | 0 | 0 | 138.0782135000918 | 245352 |
| A | repair | 1 | 1 | 1 | 53.31525159999728 | 78430 |
| A | temperature | 1 | 1 | 1 | 26.87467419996392 | 42533 |
| A | threshold | 1 | 1 | 1 | 26.23228230001405 | 42898 |
| A | overall | 5 | 3 | 4 | 53.168614299967885 | 78430 |
| B | alarms | 1 | 1 | 1 | 52.74469319998752 | 82039 |
| B | inspect | 1 | 0 | 0 | 26.503226100001484 | 17684 |
| B | io_mapping | 1 | 1 | 0 | 106.00628059997689 | 252330 |
| B | repair | 1 | 1 | 1 | 45.919423799961805 | 81085 |
| B | temperature | 1 | 1 | 1 | 26.791648300015368 | 46958 |
| B | threshold | 1 | 1 | 1 | 25.60794839996379 | 46592 |
| B | overall | 6 | 5 | 4 | 36.35553604998859 | 64021.5 |

Original results above remain unchanged. Explicit inspection regrades:

- `demo-io-mapping-6`, A: 3/5 accepted.
- `demo-io-mapping-6`, B: 5/6 accepted.
- `feeder-3`, A: 3/5 accepted.
- `feeder-3`, B: 6/6 accepted.
- `feeder-alarms-2`, A: 4/5 accepted.
- `feeder-alarms-2`, B: 5/6 accepted.

Measured Python source verified against Git (CRLF/LF normalized):

