# 20261123T203810Z-2c2576bd

Provider/model: `deepseek` / `deepseek-flash`.
Harness base revision: `a28ec8a8e9609d62bbd44d1944155deb0df20558`; dirty: `True`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Static recognized-subset acceptance; PLC runtime behavior remains unverified.
- API client/model experiment, distinct from ChatGPT UI.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.
- Mutable provider alias: matching model IDs do not guarantee identical weights over time.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| A | alarms | 1 | 1 | 1 | 27.862682999984827 | 69380 |
| A | io_mapping | 1 | 0 | 0 | 100.22077559999889 | 1944361 |
| A | temperature | 1 | 1 | 1 | 17.642244999995455 | 59454 |
| A | threshold | 1 | 1 | 1 | 19.36190199997509 | 63596 |
| A | overall | 4 | 3 | 3 | 23.612292499979958 | 66488.0 |
| B | alarms | 1 | 1 | 1 | 26.05883220001124 | 68068 |
| B | io_mapping | 1 | 0 | 0 | 98.91025549999904 | 2576289 |
| B | repair | 1 | 1 | 1 | 23.11025399999926 | 84357 |
| B | temperature | 1 | 1 | 1 | 20.426979300013045 | 65739 |
| B | threshold | 1 | 1 | 1 | 18.303670099994633 | 64876 |
| B | overall | 5 | 4 | 4 | 23.11025399999926 | 68068 |

Original results above remain unchanged. Explicit inspection regrades:


Measured Python source verified against Git (CRLF/LF normalized):

