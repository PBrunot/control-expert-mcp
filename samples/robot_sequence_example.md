# M580 robot sequence reconstruction example

## Example project

- Project: [demo_ControlExpert_M580.STU](demo_ControlExpert_M580.STU)
- CPU: M580 BME P58 3040, firmware 03.20.
- Inspected with Control Expert 16.4 on 2026-11-21.
- Main source: `MAST / Packaging_Robot` (SFC chart and seven ST actions).
- Supporting source: `MAST / Packaging` and `MAST / Transportation_Belt`.
- Method: offline source inspection; no PLC execution or live connection.

## Query prompt

> Load `samples\demo_ControlExpert_M580.STU`. With the loaded project, reconstruct the robot sequence, including every transition, the five/ten-piece branches, timers, and return to the initial step.

Original query:

> with the loaded project, Reconstruct the robot sequence, including every transition, the five/ten-piece branches, timers, and return to the initial step

## Reply

The robot sequence reconstructed from the sample is below. All conditions use the `Robot_one.` prefix unless shown otherwise.

| From | Exact transition condition | To |
|---|---|---|
| `Start_Robot` | `robot_running` | `Rotation` |
| `Rotation` | `Rotation_left_done` | `Arm_1` |
| `Arm_1` | `Arm_one_done` | `Arm_2` |
| `Arm_2` | `packaging_5` | `five` |
| `Arm_2` | `packaging_10` | `ten` |
| `five` | `rotation_right_five_done` | `Packaging` |
| `ten` | `rotation_right_ten_done` | `Packaging` |
| `Packaging` | `material_down_done` | Jump to `Start_Robot` |

The actions behind those transitions are:

1. **`Start_Robot` → initialization.** `Init_Robot` assigns `robot_running := Start_process` and clears `material_down_done`. When the process is enabled, the chart enters `Rotation`.

2. **`Rotation` → rotate left.** A rising edge of `Belt_running`, while `robot_running` is true, sets `Rotation_left`. `Robot_rotation`, a **1-second TON**, then sets `Rotation_left_done` and clears the rotation command. Separately, after **300 ms** in this step, `init` is set while the robot is running and `Rotation_left` is false.

3. **`Arm_1` → move the first arm.** With `Rotation_left_done` true and step elapsed time **greater than 100 ms**, set `Arm_one`. `Arm_1_Timer`, a **1-second TON**, sets `Arm_one_done`; the action clears `Arm_one`, its completion intermediate, and `Rotation_left_done`.

4. **`Arm_2` → move the second arm and select a branch.** With `Arm_one_done` true and step elapsed time **greater than 100 ms**, set `Arm_two`. `Arm_2_Timer`, a **1-second TON**, sets `Arm_two_done` and clears the preceding movement flags. Branch selection then requires:
   - `Arm_two_done AND five_pices` → `packaging_5`.
   - `Arm_two_done AND ten_pices` → `packaging_10`.

   The separate ladder section `Packaging` latches these selections from rising edges of `hb_five` and `hb_ten`, resetting the opposite selection. If both selections are true, the later ten-piece logic wins.

5. **`five` or `ten` → pick material and rotate right.** Both branches perform the same timed sequence, using different right-rotation flags:
   - After step elapsed time **greater than 200 ms**, with `Arm_two_done` true, set `Taking_Material` and `Material_picked_off`.
   - `PACKAGING_TIMER`: **1-second TON**. On completion, clear `Arm_two_done` and `Taking_Material`; set `Rotation_right_five` or `Rotation_right_ten`.
   - `ROTATION_RIGHT_TIMER`: **1-second TON**. On completion, set the corresponding `rotation_right_*_done` flag and clear the rotation command.
   - The branches rejoin at `Packaging`.

6. **`Packaging` → place material and return.** Set `arm_right`, run `Arm_right_Timer` for **1 second**, then clear `Material_picked_off`, set `material_down`, clear both branch completion flags, and clear `arm_right`. `Material_down_Timer`, another **1-second TON**, then clears `material_down` and sets `material_down_done`. That transition jumps back to `Start_Robot`, where the final completion flag is cleared.

Two source details matter:

- The packaging action's expression is `five_done OR (ten_done AND Packaging.t > 200ms)`, where `five_done` and `ten_done` abbreviate `Robot_one.rotation_right_five_done` and `Robot_one.rotation_right_ten_done`. Consequently, **only the ten-piece path receives that explicit 200-ms delay**.
- Configured SFC minimum-time monitoring is **1 second** for `Arm_1`, `Arm_2`, and `Packaging`, and **2 seconds** for `five`; none is configured for `ten`. These are monitoring thresholds, separate from the explicit delays and TON timers.

The branches select a packaging mode; their action code contains **no actual five- or ten-piece counter**. This reconstruction is from static source inspection, without running the PLC sequence.

## Export error and server fix

The inspection also exposed this export failure:

```text
export_project({"path":"E:\\GitHub\\control-expert-mcp\\tmp\\robot_sequence_inspection.xef"})
Export action failed, because PLC M580 cannot export XEF file. Choose ZEF instead.
Server SCODE 0xA8A72CF4; HRESULT 0x80020009.
```

Follow-up query:

> fix that in the MCP server

Reply:

Fixed in `src/control_expert_mcp/bridge.py`. When Control Expert rejects XEF with this specific error, `export_project` retries as ZEF and returns the actual `exported` path. Existing fallback files are protected. Tool documentation and a workflow prompt are updated.

Validation: six regression tests, syntax checks, and a real export using Control Expert 16.4 with the M580 BME P58 3040, firmware 03.20. The resulting ZEF passed ZIP integrity checks. Restart the MCP server to load the fix.

The offline regression command is:

```powershell
.venv\Scripts\python.exe tools/test_project_export.py
.venv\Scripts\python.exe -m compileall -q src
```
