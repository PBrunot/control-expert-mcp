# 20261123T210125Z-simulator-4e135a7d

Provider/model: `deepseek` / `deepseek-flash`.
Harness base revision: `a28ec8a8e9609d62bbd44d1944155deb0df20558`; dirty: `True`.

- Small repetition counts are exploratory, not statistically strong comparisons.
- Sampled one-second OPC DA counter behavior on PLC Simulator; no scan-level or physical-hardware proof.
- API client/model experiment, distinct from ChatGPT UI.
- Dirty source fingerprints identify uncommitted code; do not label them a clean revision.
- Mutable provider alias: matching model IDs do not guarantee identical weights over time.

| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |
|---|---|---:|---:|---:|---:|---:|
| SIMULATOR | simulator_counter | 1 | 1 | 1 | 101.00225079999655 | 884115 |
| SIMULATOR | overall | 1 | 1 | 1 | 101.00225079999655 | 884115 |

Original results above remain unchanged. Explicit inspection regrades:


Measured Python source verified against Git (CRLF/LF normalized):

