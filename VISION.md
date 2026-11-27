# Vision and Working Guide

Internal guide for the maintainer and AI agents changing this server. User docs are in `README.md` and `docs/guide.md`; repository commands are in `AGENTS.md`.
Last updated: 2026-11-27.

## Goal

Make EcoStruxure Control Expert programmable by AI agents over MCP: create, read, build, test, and operate M340/M580/Premium/Quantum projects in all five IEC languages, starting from `new_project`, without external reference projects.

## Principles

1. **Control Expert is the oracle.** Trust authored XML only after `build_project` succeeds. "Looks right" is not validation.
2. **Author from the grammar.** Use the installed `SrcXmlSchema\*.xsd` and UDE XML specs, check with `validate_xml`, then build. Trial and error confirms a candidate; it does not define the element set.
3. **Use MCP primitives for their purpose.** Tools act, prompts guide workflows, resources carry reference knowledge. Prefer generators that emit validated XML over asking clients to hand-write it.
4. **Ship knowledge with features.** Every new capability gets a workflow prompt in `prompts.py` and, when useful, a reference or gotcha entry in `lang_reference.py`. Record a difficulty when you hit it.
5. **Safety first.** Online tools require `CE_MCP_ENABLE_ONLINE=1` and per-session consent through `configure_live_access`. Downloads, run/stop, live writes, and online-change builds (`allow_online_change`) need closed-loop approval. Test on disposable projects and the simulator or a supervised bench; never save over a real project.

## Architecture rules

- All COM calls run on the bridge's dedicated STA worker (`bridge.py`). Do not call COM from other threads.
- The bridge acquires the project write token once per session and caches it. Only one holder at a time: the Control Expert GUI and the automation client cannot both write.
- Live access goes through `live_access.py` consent checks. Never infer consent from environment variables or probing.
- COM has no live values. Symbolic live values use OFS OPC DA (`opc.py`, `opc_worker.py` in a bitness-matched Python from `CE_MCP_OPC_PYTHON`). Modbus TCP (`modbus.py`) reaches located `%M`/`%MW` only; 32-bit values are low-word-first; Modbus calls are serialized.
- Exchange-file extensions must match the XML root: Control Expert picks the import parser by extension.
- Hardware and DTM automation use secondary COM interfaces; keep the bridge's interface-query helpers.

## Authoring facts

- LD: each line accounts for all `nbColumns` cells. Edge contacts/coils (`PContact`, `NContact`, `PCoil`, `NCoil`) need `EBOOL` variables.
- FBD: block height is 4 + visible input pins; pin row is `posY + 4 + i`; link endpoints must match the pin grid (otherwise E1189).
- SFC: steps on even `posY`, transitions on odd.
- Simulator: the first transfer may need seeding from the GUI ("Family check failed"); see `docs/guide.md#plc-and-simulator-access`.

## Working conventions

- Run offline tests (`python -m unittest discover -s tools -p "test_*.py"`) and `python -m compileall -q src` before handing off.
- For COM changes, validate import, analyze, and build round trips on a real installation and record CPU/version, prerequisites, commands, and results.
- Review `tools/bigtest/` and other integration scripts before running them; they can modify projects or terminate Control Expert.
- Update README, `docs/guide.md`, and prompts when capabilities change.
- Never commit customer projects, vendor binaries or manuals, generated archives, or credentials.

## Known issues

- `create_task` (e.g. FAST) has returned "Bad parameter (0x80020009)"; not yet verified fixed.
