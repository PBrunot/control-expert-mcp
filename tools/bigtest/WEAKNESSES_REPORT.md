# Big recreation test: DR001 Dabouq Reservoir

Scripts `01_*.py`-`10_*.py` rebuild an M580 HSBY remote-EIO project (BME H58 2040,
437 variables, 86 DDTs/20 DFBs, 19 MAST sections, 17 Modbus DTMs) through MCP
tools only, using the reference STU read-only. The customer project is not in the
repository.

**Warning:** `common.kill_strays()` force-kills `ControlExpert.exe` and
`psbroker.exe` and deletes `.ztx` write tokens before each phase. Run only on a
dedicated machine.

## Result

- Hardware, DDTs, DFBs, variables, sections (order preserved), Modbus DTMs, CPU
  Ethernet/security and project settings are reproduced with no tool failures.
- Build stops at 49 errors, all from the two headless limits below.

## Remaining limits (headless CE automation, not tool bugs)

- **HSBY EtherNet/IP scanner validation** ("EIP option must be checked for the
  HSBY cpu", 1 error) is computed from DTM build state produced only by
  `BuildControlInformation`/`UpdateDtmPlcLink`, which fail headlessly ("DTM not
  linked with PLC control"). No stored flag can be patched. Non-HSBY M580 passes
  via the security bits.
- **AHI HART gateway DTMs** (`BME AHI 0812`, 48 HART_SIGNALS errors): `add_dtm`
  cannot create them; they come only from the interactive CPU DTM editor.

## Fixed (present in `bridge.py`/`server.py`)

`export_xml(kind="ddt")`; `replace_rack`/`replace_io_module`;
`get_project_setting`/`set_project_settings` (e.g. `multiAssign` for E1203);
`configure_cpu_ethernet` `ip_b`/`ip_d`; section imports strip `Owner`-attributed
device-DDT declarations (`_strip_managed_devddt_decls`, prevented ~376 duplicate
errors); `set_dtm_address` STB island fallback; `save_project(None)` saves back
to the original path after a ZEF patch.
