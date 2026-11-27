# 20261127T192306Z-simulator-30511c7e

Provider/model: `claude-code` / `claude-haiku-4-5-20251001`.
Harness base revision: `8432871bba754e95819570a1addd000608242dce`; dirty: `True`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Sampled one-second OPC DA counter behavior on PLC Simulator; no scan-level or physical-hardware proof.
- Claude Code CLI agent loop (subscription login, built-in tools disabled, server instructions as replacement system prompt); distinct from interactive Claude Code defaults.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| SIMULATOR | simulator_counter | 1 | 0 | 1 | 150.46403020003345 | 820066 |
| SIMULATOR | overall | 1 | 0 | 1 | 150.46403020003345 | 820066 |

Original results above remain unchanged. Explicit inspection regrades:


Measured Python source verified against Git (CRLF/LF normalized):

