# M580 application signal and I/O mapping

Project: [demo_ControlExpert_M580.STU](demo_ControlExpert_M580.STU). Inspected offline on 2026-11-21 with Control Expert 16.4. CPU: BME P58 3040, firmware 03.20. All listed field modules are on PLC bus 0, local drop 0, rack 0.

## Query prompt

> Produce a table linking application signals to I/O addresses or device-DDT fields, modules, and channels. Flag signals without a physical mapping. Results shall me saved too in a md file.

## Findings

There are 163 global instances including generated SFC state instances: four mapped discrete outputs, four mapped analog channel structures, three module-owned device-DDT instances, one CPU communication DDT, two internal-memory instances, and 149 instances without a physical mapping. The 23 Robot_one members are additionally expanded below.

Only Machine_running is referenced in executable application logic among the 11 physical I/O instances. L0, L1, L2, the analog channel structures, and the three field-module device DDTs have no executable reference in the exported application sections or SFC actions. No assignment connecting the process or robot signals to those device-DDT fields was found. A device-DDT instance is a real hardware interface even when list_variables returns no address; its Owner attribute and IOConf deviceDDT binding establish its module.

UNMAPPED means no declared physical address, module owner, or explicit bridge to field I/O was found. It does not imply the signal should be wired: timers, calculated values, commands from operator screens, and SFC state are intentionally software data. %MW locations are internal memory, not physical I/O.

## Configured field modules

| Slot | Module | Version | Addressing mode | Channels | Application mapping |
| --- | --- | --- | --- | --- | --- |
| 2 | BMXDDI3202K | 02.00 | topologic | 0–31 | No named %I signal |
| 3 | BMXDDO1602 | 02.00 | topologic | 0–15 | L0, L1, L2, Machine_running |
| 4 | BMXAMI0410 | 01.00 | topologic | 0–3 | Analog_input_0 through Analog_input_3 |
| 5 | BMXDDI3202K | 02.00 | device DDT | 0–31 | DDI3202K_0_5 |
| 6 | BMXDDO1602 | 02.00 | device DDT | 0–15 | DDO1602_0_6 |
| 7 | BMXAMI0410 | 01.00 | device DDT | 0–3 | AMI0410_0_7 |

## Signals with physical mappings

| Signal | Type | Address or DDT | Module | Channel | Status | Meaning | Executable sections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `AMI0410_0_7` | `T_U_ANA_STD_IN_4` | `AMI0410_0_7` | Rack 0, slot 7: BMXAMI0410 | 0–3 | PHYSICAL DEVICE DDT | Owner \0.0\0.7; channel fields listed below. No process alias found. | No executable reference found |
| `Analog_input_0` | `T_ANA_IN_GEN` | `%CH0.4.0` | Rack 0, slot 4: BMXAMI0410 | 0 | PHYSICAL CHANNEL STRUCTURE | Channel interface; no process alias found. | No executable reference found |
| `Analog_input_1` | `T_ANA_IN_GEN` | `%CH0.4.1` | Rack 0, slot 4: BMXAMI0410 | 1 | PHYSICAL CHANNEL STRUCTURE | Channel interface; no process alias found. | No executable reference found |
| `Analog_input_2` | `T_ANA_IN_GEN` | `%CH0.4.2` | Rack 0, slot 4: BMXAMI0410 | 2 | PHYSICAL CHANNEL STRUCTURE | Channel interface; no process alias found. | No executable reference found |
| `Analog_input_3` | `T_ANA_IN_GEN` | `%CH0.4.3` | Rack 0, slot 4: BMXAMI0410 | 3 | PHYSICAL CHANNEL STRUCTURE | Channel interface; no process alias found. | No executable reference found |
| `DDI3202K_0_5` | `T_U_DIS_STD_IN_32` | `DDI3202K_0_5` | Rack 0, slot 5: BMXDDI3202K | 0–31 | PHYSICAL DEVICE DDT | Owner \0.0\0.5; channel fields listed below. No process alias found. | No executable reference found |
| `DDO1602_0_6` | `T_U_DIS_STD_OUT_16` | `DDO1602_0_6` | Rack 0, slot 6: BMXDDO1602 | 0–15 | PHYSICAL DEVICE DDT | Owner \0.0\0.6; channel fields listed below. No process alias found. | No executable reference found |
| `L0` | `EBOOL` | `%Q0.3.0` | Rack 0, slot 3: BMXDDO1602 | 0 | PHYSICAL OUTPUT | RED LED | No executable reference found |
| `L1` | `EBOOL` | `%Q0.3.1` | Rack 0, slot 3: BMXDDO1602 | 1 | PHYSICAL OUTPUT | YELLOW LED | No executable reference found |
| `L2` | `EBOOL` | `%Q0.3.2` | Rack 0, slot 3: BMXDDO1602 | 2 | PHYSICAL OUTPUT | GREEN LED | No executable reference found |
| `Machine_running` | `EBOOL` | `%Q0.3.3` | Rack 0, slot 3: BMXDDO1602 | 3 | PHYSICAL OUTPUT | Output for Machine running | Start_process |

## Device-DDT channel fields

The following are hardware interface fields, not additional process aliases. Channel indices come from installed Schneider type definitions; the instance-to-module binding comes from the project. Numeric %I/%Q aliases are not invented for modules configured in device-DDT mode. Each row is a distinct channel.

| Device-DDT value field | Module | Rack / slot | Channel | Direction | Application link |
| --- | --- | --- | --- | --- | --- |
| `DDI3202K_0_5.DIS_CH_IN[0].VALUE` | BMXDDI3202K | 0 / 5 | 0 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[1].VALUE` | BMXDDI3202K | 0 / 5 | 1 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[2].VALUE` | BMXDDI3202K | 0 / 5 | 2 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[3].VALUE` | BMXDDI3202K | 0 / 5 | 3 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[4].VALUE` | BMXDDI3202K | 0 / 5 | 4 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[5].VALUE` | BMXDDI3202K | 0 / 5 | 5 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[6].VALUE` | BMXDDI3202K | 0 / 5 | 6 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[7].VALUE` | BMXDDI3202K | 0 / 5 | 7 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[8].VALUE` | BMXDDI3202K | 0 / 5 | 8 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[9].VALUE` | BMXDDI3202K | 0 / 5 | 9 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[10].VALUE` | BMXDDI3202K | 0 / 5 | 10 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[11].VALUE` | BMXDDI3202K | 0 / 5 | 11 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[12].VALUE` | BMXDDI3202K | 0 / 5 | 12 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[13].VALUE` | BMXDDI3202K | 0 / 5 | 13 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[14].VALUE` | BMXDDI3202K | 0 / 5 | 14 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[15].VALUE` | BMXDDI3202K | 0 / 5 | 15 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[16].VALUE` | BMXDDI3202K | 0 / 5 | 16 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[17].VALUE` | BMXDDI3202K | 0 / 5 | 17 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[18].VALUE` | BMXDDI3202K | 0 / 5 | 18 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[19].VALUE` | BMXDDI3202K | 0 / 5 | 19 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[20].VALUE` | BMXDDI3202K | 0 / 5 | 20 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[21].VALUE` | BMXDDI3202K | 0 / 5 | 21 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[22].VALUE` | BMXDDI3202K | 0 / 5 | 22 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[23].VALUE` | BMXDDI3202K | 0 / 5 | 23 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[24].VALUE` | BMXDDI3202K | 0 / 5 | 24 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[25].VALUE` | BMXDDI3202K | 0 / 5 | 25 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[26].VALUE` | BMXDDI3202K | 0 / 5 | 26 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[27].VALUE` | BMXDDI3202K | 0 / 5 | 27 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[28].VALUE` | BMXDDI3202K | 0 / 5 | 28 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[29].VALUE` | BMXDDI3202K | 0 / 5 | 29 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[30].VALUE` | BMXDDI3202K | 0 / 5 | 30 | Input | No process alias or executable use found |
| `DDI3202K_0_5.DIS_CH_IN[31].VALUE` | BMXDDI3202K | 0 / 5 | 31 | Input | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[0].VALUE` | BMXDDO1602 | 0 / 6 | 0 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[1].VALUE` | BMXDDO1602 | 0 / 6 | 1 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[2].VALUE` | BMXDDO1602 | 0 / 6 | 2 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[3].VALUE` | BMXDDO1602 | 0 / 6 | 3 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[4].VALUE` | BMXDDO1602 | 0 / 6 | 4 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[5].VALUE` | BMXDDO1602 | 0 / 6 | 5 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[6].VALUE` | BMXDDO1602 | 0 / 6 | 6 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[7].VALUE` | BMXDDO1602 | 0 / 6 | 7 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[8].VALUE` | BMXDDO1602 | 0 / 6 | 8 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[9].VALUE` | BMXDDO1602 | 0 / 6 | 9 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[10].VALUE` | BMXDDO1602 | 0 / 6 | 10 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[11].VALUE` | BMXDDO1602 | 0 / 6 | 11 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[12].VALUE` | BMXDDO1602 | 0 / 6 | 12 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[13].VALUE` | BMXDDO1602 | 0 / 6 | 13 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[14].VALUE` | BMXDDO1602 | 0 / 6 | 14 | Output | No process alias or executable use found |
| `DDO1602_0_6.DIS_CH_OUT[15].VALUE` | BMXDDO1602 | 0 / 6 | 15 | Output | No process alias or executable use found |
| `AMI0410_0_7.ANA_CH_IN[0].ANA.VALUE` | BMXAMI0410 | 0 / 7 | 0 | Analog input | No process alias or executable use found |
| `AMI0410_0_7.ANA_CH_IN[1].ANA.VALUE` | BMXAMI0410 | 0 / 7 | 1 | Analog input | No process alias or executable use found |
| `AMI0410_0_7.ANA_CH_IN[2].ANA.VALUE` | BMXAMI0410 | 0 / 7 | 2 | Analog input | No process alias or executable use found |
| `AMI0410_0_7.ANA_CH_IN[3].ANA.VALUE` | BMXAMI0410 | 0 / 7 | 3 | Analog input | No process alias or executable use found |

Each of these three device DDTs also exposes MOD_HEALTH and MOD_FLT at module level. Discrete channel elements expose CH_HEALTH. Analog channel elements expose CH_HEALTH, CH_WARNING, MEASURE_STS and additional status/forcing fields; ANA.VALUE is the measured-value field. These status fields are hardware diagnostics, not extra field channels.

## Complete global signal inventory

This inventory covers every global instance returned by list_variables, including FB instances and generated SFC state. Executable sections are lexical references in the exported program XML; they do not distinguish read versus write and exclude animation tables and operator screens. A section/state name may also occur in its own definition.

| Signal | Type | Address or DDT | Module | Channel | Mapping status | Meaning or evidence | Executable sections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Alert_1` | `EBOOL` | — | — | — | UNMAPPED | Alert for temperature to low | Alarming |
| `Alert_2` | `EBOOL` | — | — | — | UNMAPPED | Alert for temperature to high | Alarming |
| `Alert_3` | `EBOOL` | — | — | — | UNMAPPED | Alert for feeder empty | Alarming |
| `AMI0410_0_7` | `T_U_ANA_STD_IN_4` | `AMI0410_0_7` | Rack 0, slot 7: BMXAMI0410 | 0–3 | PHYSICAL DEVICE DDT | Owner \0.0\0.7; channel fields listed below. No process alias found. | No executable reference found |
| `Analog_input_0` | `T_ANA_IN_GEN` | `%CH0.4.0` | Rack 0, slot 4: BMXAMI0410 | 0 | PHYSICAL CHANNEL STRUCTURE | Channel interface; no process alias found. | No executable reference found |
| `Analog_input_1` | `T_ANA_IN_GEN` | `%CH0.4.1` | Rack 0, slot 4: BMXAMI0410 | 1 | PHYSICAL CHANNEL STRUCTURE | Channel interface; no process alias found. | No executable reference found |
| `Analog_input_2` | `T_ANA_IN_GEN` | `%CH0.4.2` | Rack 0, slot 4: BMXAMI0410 | 2 | PHYSICAL CHANNEL STRUCTURE | Channel interface; no process alias found. | No executable reference found |
| `Analog_input_3` | `T_ANA_IN_GEN` | `%CH0.4.3` | Rack 0, slot 4: BMXAMI0410 | 3 | PHYSICAL CHANNEL STRUCTURE | Channel interface; no process alias found. | No executable reference found |
| `Arm_1` | `SFCSTEP_STATE` | — | — | — | UNMAPPED |  | Packaging_Robot |
| `Arm_1_Timer` | `TON` | — | — | — | UNMAPPED | Timer for movement arm 1 | Packaging_Robot |
| `Arm_2` | `SFCSTEP_STATE` | — | — | — | UNMAPPED |  | Packaging_Robot |
| `Arm_2_Timer` | `TON` | — | — | — | UNMAPPED | Timer for movement arm 2 | Packaging_Robot |
| `Arm_right_Timer` | `TON` | — | — | — | UNMAPPED | Timer for movement arm right | Packaging_Robot |
| `AUX_1` | `EBOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `Aux_2` | `EBOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `Aux_4` | `EBOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `Axis_ready` | `BOOL` | — | — | — | UNMAPPED |  | No executable reference found |
| `Belt_motor` | `RS` | — | — | — | UNMAPPED | Transportation belt motor | Transportation_Belt |
| `Belt_running` | `EBOOL` | — | — | — | UNMAPPED | Transportation belt running | Transportation_Belt, Packaging_Robot |
| `BMEP58_ECPU_EXT` | `T_BMEP58_ECPU_EXT` | `BMEP58_ECPU_EXT` | Rack 0, slot 0: BMEP583040 | — | CPU COMMUNICATION DDT | Managed CPU Ethernet/communication interface; not a field I/O channel. | No executable reference found |
| `BP0` | `EBOOL` | — | — | — | UNMAPPED | Left push button | No executable reference found |
| `BP1` | `EBOOL` | — | — | — | UNMAPPED | Middle push button | No executable reference found |
| `Check` | `EBOOL` | — | — | — | UNMAPPED | Result of conditions; must be true | diagnostic |
| `Cmeasured_temp` | `REAL` | — | — | — | UNMAPPED | Calculating variable for measured temperature | Feeder |
| `COM_CAN` | `BOOL` | — | — | — | UNMAPPED |  | No executable reference found |
| `Cond_ok` | `BOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `Conveying_motor` | `MotorTwoDirections` | — | — | — | UNMAPPED | Conveying screw motor | Forming |
| `Conveying_screw` | `BOOL` | — | — | — | UNMAPPED | Conveying screw | Forming |
| `cooling_duration` | `TIME` | — | — | — | UNMAPPED |  | adjust_steps |
| `cooling_duration_int` | `INT` | — | — | — | UNMAPPED |  | adjust_steps |
| `cooling_monitoring` | `SFCSTEP_TIMES` | — | — | — | UNMAPPED |  | adjust_steps |
| `cooling_step_max_INT` | `INT` | — | — | — | UNMAPPED |  | adjust_steps |
| `cooling_step_min_INT` | `INT` | — | — | — | UNMAPPED |  | adjust_steps |
| `CS_A` | `BOOL` | — | — | — | UNMAPPED | Internal bit for conveying screw | Forming |
| `Current_position` | `DINT` | `%MW10` | — | — | NO PHYSICAL MAPPING — MEMORY | PLC internal word memory; not an I/O channel. | No executable reference found |
| `cv_Material_A` | `INT` | — | — | — | UNMAPPED | Internal variable for Material A | Start_process, Weighing_Material_B |
| `cv_material_A_2` | `INT` | — | — | — | UNMAPPED | Internal variable for Material A | Weighing_Material_B |
| `cv_Material_B` | `INT` | — | — | — | UNMAPPED | Internal variable for Material B | Start_process, Weighing_Material_B |
| `cv_material_B_2` | `INT` | — | — | — | UNMAPPED | Internal variable for Material B | Weighing_Material_B |
| `cv_setpoint` | `INT` | — | — | — | UNMAPPED | Internal variable for temperature setpoint | Heating |
| `DDI3202K_0_5` | `T_U_DIS_STD_IN_32` | `DDI3202K_0_5` | Rack 0, slot 5: BMXDDI3202K | 0–31 | PHYSICAL DEVICE DDT | Owner \0.0\0.5; channel fields listed below. No process alias found. | No executable reference found |
| `DDO1602_0_6` | `T_U_DIS_STD_OUT_16` | `DDO1602_0_6` | Rack 0, slot 6: BMXDDO1602 | 0–15 | PHYSICAL DEVICE DDT | Owner \0.0\0.6; channel fields listed below. No process alias found. | No executable reference found |
| `diag_ctrl` | `BOOL` | — | — | — | UNMAPPED |  | No executable reference found |
| `diag_in_wp_1` | `BOOL` | — | — | — | UNMAPPED |  | diag_system, Watchpoint, diagnostic |
| `diag_in_wp_2` | `BOOL` | — | — | — | UNMAPPED |  | diag_system, Watchpoint, diagnostic |
| `diag_in_wp_3` | `BOOL` | — | — | — | UNMAPPED |  | diag_system, Watchpoint, diagnostic |
| `diag_in_wp_4` | `BOOL` | — | — | — | UNMAPPED |  | diag_system, Watchpoint, diagnostic |
| `diag_in_wp_5` | `BOOL` | — | — | — | UNMAPPED |  | diag_system, Watchpoint, diagnostic |
| `diag_int` | `INT` | — | — | — | UNMAPPED |  | diag_system |
| `diag_out_wp_1` | `BOOL` | — | — | — | UNMAPPED |  | Watchpoint |
| `Diag_overflow` | `INT` | — | — | — | UNMAPPED |  | diag_system |
| `diag_test` | `BOOL` | — | — | — | UNMAPPED |  | Watchpoint |
| `enable_diag` | `BOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `ERR_CAN_HANDLER` | `UDINT` | — | — | — | UNMAPPED |  | No executable reference found |
| `fdbk_ET_conveyer` | `TIME` | — | — | — | UNMAPPED |  | Forming |
| `fdbk_ET_forming` | `TIME` | — | — | — | UNMAPPED |  | Forming |
| `feeder_empty` | `BOOL` | — | — | — | UNMAPPED | Material feeder empty | Feeder |
| `feeder_full` | `BOOL` | — | — | — | UNMAPPED | Material feeder full | Feeder |
| `Feeder_monitoring` | `ALRM_DIA` | — | — | — | UNMAPPED | No material in feeder/refilling...... | Alarming |
| `Feeder_state` | `INT` | — | — | — | UNMAPPED | Feeder state | Feeder |
| `Fill_feeder` | `BOOL` | — | — | — | UNMAPPED | Fill feeder | Mixer |
| `five` | `SFCSTEP_STATE` | — | — | — | UNMAPPED |  | Packaging_Robot |
| `five_pices` | `BOOL` | — | — | — | UNMAPPED | Packaging 5 pices | Packaging, Packaging_Robot |
| `Flapp` | `TP` | — | — | — | UNMAPPED | Pulse for flapp | Weighing_Material_A, Weighing_Material_B |
| `Flapp_A` | `BOOL` | — | — | — | UNMAPPED | Internal variable (Flapp Material A) | Weighing_Material_A, Weighing_Material_B |
| `Flapp_B` | `BOOL` | — | — | — | UNMAPPED | Internal variable (Flapp Material B) | Weighing_Material_A, Weighing_Material_B |
| `Flapp_closed` | `BOOL` | — | — | — | UNMAPPED | Flapp closed | Weighing_Material_B |
| `Flapp_open` | `BOOL` | — | — | — | UNMAPPED | Flapp open | Weighing_Material_A, Weighing_Material_B |
| `Forming` | `EBOOL` | — | — | — | UNMAPPED | Forming material in progress | Feeder, Forming, Transportation_Belt |
| `Forming_motor` | `MotorTwoDirections` | — | — | — | UNMAPPED | Forming motor | Forming |
| `hb_five` | `EBOOL` | — | — | — | UNMAPPED | Internal Bit for five pieces | Packaging |
| `hb_Packaging` | `BOOL` | — | — | — | UNMAPPED | Internal bit packaging | Packaging_Robot |
| `hb_rotation_right` | `BOOL` | — | — | — | UNMAPPED | Internal bit robot rotation right | Packaging_Robot |
| `hb_ten` | `EBOOL` | — | — | — | UNMAPPED | Internal Bit for ten pieces | Packaging |
| `Heating_control` | `Heating` | — | — | — | UNMAPPED | Heating control | Heating |
| `heating_duration` | `TIME` | — | — | — | UNMAPPED |  | adjust_steps |
| `heating_duration_int` | `INT` | — | — | — | UNMAPPED |  | adjust_steps |
| `heating_monitoring` | `SFCSTEP_TIMES` | — | — | — | UNMAPPED |  | adjust_steps |
| `heating_step_max_INT` | `INT` | — | — | — | UNMAPPED |  | adjust_steps |
| `heating_step_min_INT` | `INT` | — | — | — | UNMAPPED |  | adjust_steps |
| `Ind` | `INT` | — | — | — | UNMAPPED |  | No executable reference found |
| `Index` | `INT` | — | — | — | UNMAPPED |  | diag_system |
| `Init_motion` | `BOOL` | — | — | — | UNMAPPED | Validate the sections that manage motion | No executable reference found |
| `L0` | `EBOOL` | `%Q0.3.0` | Rack 0, slot 3: BMXDDO1602 | 0 | PHYSICAL OUTPUT | RED LED | No executable reference found |
| `L1` | `EBOOL` | `%Q0.3.1` | Rack 0, slot 3: BMXDDO1602 | 1 | PHYSICAL OUTPUT | YELLOW LED | No executable reference found |
| `L2` | `EBOOL` | `%Q0.3.2` | Rack 0, slot 3: BMXDDO1602 | 2 | PHYSICAL OUTPUT | GREEN LED | No executable reference found |
| `Ls_close` | `BOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `Ls_open` | `BOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `Machine_running` | `EBOOL` | `%Q0.3.3` | Rack 0, slot 3: BMXDDO1602 | 3 | PHYSICAL OUTPUT | Output for Machine running | Start_process |
| `Material_A` | `INT` | — | — | — | UNMAPPED | Value material A | Weighing_Material_B |
| `Material_a_in` | `BOOL` | — | — | — | UNMAPPED | Internal bit for material A in feeder | Weighing_Material_A |
| `material_a_value` | `INT` | — | — | — | UNMAPPED | Value material A | Start_process, Weighing_Material_A, Feeder |
| `Material_B` | `INT` | — | — | — | UNMAPPED | Value material B | Weighing_Material_B |
| `Material_b_in` | `BOOL` | — | — | — | UNMAPPED | Internal bit for material B in feeder | Weighing_Material_A, Weighing_Material_B |
| `material_b_value` | `INT` | — | — | — | UNMAPPED | Starting value for weighing material B | Start_process, Weighing_Material_B, Feeder |
| `Material_down_Timer` | `TON` | — | — | — | UNMAPPED | Timer for material down | Packaging_Robot |
| `Material_in` | `INT` | — | — | — | UNMAPPED | Internal bit for material in feeder | Feeder |
| `Material_ok` | `BOOL` | — | — | — | UNMAPPED | Material value ok | Feeder, Forming, Transportation_Belt |
| `Material_picked_off` | `EBOOL` | — | — | — | UNMAPPED | Material picked up from robot | Packaging_Robot |
| `Measured_temp` | `INT` | — | — | — | UNMAPPED | Measurement of temperature | Heating, Feeder |
| `minus_10_percent` | `BOOL` | — | — | — | UNMAPPED | Heating input power -10% | Heating |
| `minus_1_percent` | `BOOL` | — | — | — | UNMAPPED | Heating input power -1% | Heating |
| `minus_5_percent` | `BOOL` | — | — | — | UNMAPPED | Heating input power -5% | Heating |
| `MixerA` | `BOOL` | — | — | — | UNMAPPED | Internal variable mixer | Mixer |
| `MixerB` | `BOOL` | — | — | — | UNMAPPED | Internal variable mixer | Mixer |
| `MixerC` | `BOOL` | — | — | — | UNMAPPED |  | Mixer |
| `Mixing` | `BOOL` | — | — | — | UNMAPPED | Mixing in progress | Weighing_Material_B, Mixer |
| `Mixing_done` | `EBOOL` | — | — | — | UNMAPPED | Mixing done | Weighing_Material_A, Mixer, Feeder |
| `Mixing_motor` | `TP` | — | — | — | UNMAPPED | Pulse for mixing motor | Mixer |
| `monostable1` | `TP` | — | — | — | UNMAPPED |  | Forming |
| `monostable2` | `TP` | — | — | — | UNMAPPED |  | Forming |
| `Ms_10` | `EBOOL` | — | — | — | UNMAPPED | Variable with 10ms timbase | Weighing_Material_A, Heating |
| `Ms_100` | `EBOOL` | — | — | — | UNMAPPED | Variable with 100ms timebase | Weighing_Material_A, Heating |
| `new_material_demand` | `EBOOL` | — | — | — | UNMAPPED | New material for feeder demandet | Weighing_Material_A, Feeder, Alarming |
| `Packaging` | `SFCSTEP_STATE` | — | — | — | UNMAPPED |  | Packaging, Packaging_Robot |
| `Packaging_Robot` | `SFCCHART_STATE` | — | — | — | UNMAPPED |  | Packaging_Robot |
| `Packaging_Timer` | `TON` | — | — | — | UNMAPPED | Timer for packaging | Packaging_Robot |
| `plus_10_percent` | `BOOL` | — | — | — | UNMAPPED | Heating input power +10% | Heating |
| `plus_1_percent` | `BOOL` | — | — | — | UNMAPPED | Heating input power +1% | Heating |
| `plus_5_percent` | `BOOL` | — | — | — | UNMAPPED | Heating input power +5% | Heating |
| `Position_Order` | `DINT` | — | — | — | UNMAPPED |  | No executable reference found |
| `Read_position` | `BOOL` | — | — | — | UNMAPPED | To read the axis position | No executable reference found |
| `ready_to_mix` | `BOOL` | — | — | — | UNMAPPED | Mixer ready | Weighing_Material_A, Weighing_Material_B, Mixer |
| `recipe` | `ARRAY[0..5] OF recipe` | `%MW100` | — | — | NO PHYSICAL MAPPING — MEMORY | PLC internal word memory; not an I/O channel. | No executable reference found |
| `Refill_feeder` | `TON` | — | — | — | UNMAPPED | Timer for refill feeder | Mixer |
| `Robot_one` | `Robot` | — | — | — | UNMAPPED | Robot one | Packaging_Robot |
| `Robot_rotation` | `TON` | — | — | — | UNMAPPED | Timer for robot rotation | Packaging_Robot |
| `Rotation` | `SFCSTEP_STATE` | — | — | — | UNMAPPED |  | Packaging_Robot |
| `Rotation_right_Timer` | `TON` | — | — | — | UNMAPPED | Timer for rotation right | Packaging_Robot |
| `Sec` | `EBOOL` | — | — | — | UNMAPPED | Variable with 1sec. timebase | Weighing_Material_A, Weighing_Material_B, Mixer, Heating, Feeder, Forming |
| `Setpoint_temp` | `REAL` | — | — | — | UNMAPPED | Setpoint for temperature | Heating, Feeder |
| `Speed_Pot` | `UDINT` | — | — | — | UNMAPPED | Speed from potentiometer | No executable reference found |
| `Start` | `BOOL` | — | — | — | UNMAPPED | Start process | Start_process, Weighing_Material_A, Weighing_Material_B, Heating, Forming |
| `Start_process` | `EBOOL` | — | — | — | UNMAPPED | Internal variable for process start | Start_process, Weighing_Material_A, Heating, Forming, Transportation_Belt, Packaging_Robot |
| `Start_Robot` | `SFCSTEP_STATE` | — | — | — | UNMAPPED |  | Packaging_Robot |
| `Stop` | `BOOL` | — | — | — | UNMAPPED | Stop process | Start_process, Forming |
| `SWITCH0` | `EBOOL` | — | — | — | UNMAPPED | Right Switch | No executable reference found |
| `Table` | `ARRAY[0..10] OF INT` | — | — | — | UNMAPPED |  | diag_system |
| `Temp_fault_1` | `EBOOL` | — | — | — | UNMAPPED | Fault for temperature to low | Heating, Alarming |
| `Temp_fault_2` | `EBOOL` | — | — | — | UNMAPPED | Fault for temperature to high | Heating, Alarming |
| `Temp_ok` | `BOOL` | — | — | — | UNMAPPED | Temperature ok | Feeder, Forming, Transportation_Belt |
| `Temperature_monitoring_1` | `ALRM_DIA` | — | — | — | UNMAPPED | Temp. low => Increase Temp. Setpoint | Alarming |
| `Temperature_monitoring_2` | `ALRM_DIA` | — | — | — | UNMAPPED | Temp. high => Decrease Temp. Setpoit | Alarming |
| `ten` | `SFCSTEP_STATE` | — | — | — | UNMAPPED |  | Packaging_Robot |
| `ten_pices` | `BOOL` | — | — | — | UNMAPPED | Packaging 10 pices | Packaging, Packaging_Robot |
| `test` | `BOOL` | — | — | — | UNMAPPED |  | Forming, diag_system |
| `TP_Mixing_done` | `TP` | — | — | — | UNMAPPED | Pulse for mixing done | Mixer |
| `Valve_1` | `EBOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `Valve_2` | `EBOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `Valve_3` | `EBOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `Valve_4` | `EBOOL` | — | — | — | UNMAPPED |  | diagnostic |
| `Valve_A_closed` | `EBOOL` | — | — | — | UNMAPPED | Material valve A closed | Weighing_Material_A, Weighing_Material_B |
| `Valve_A_open` | `EBOOL` | — | — | — | UNMAPPED | Material valve A open | Weighing_Material_A, Weighing_Material_B |
| `Valve_B_closed` | `EBOOL` | — | — | — | UNMAPPED | Material valve B closed | Weighing_Material_A, Weighing_Material_B, Mixer |
| `Valve_B_open` | `EBOOL` | — | — | — | UNMAPPED | Material valve B open | Weighing_Material_A, Weighing_Material_B |
| `Valve_selection` | `ALRM_DIA` | — | — | — | UNMAPPED | Valves selection fault | diagnostic |
| `Var_1` | `INT` | — | — | — | UNMAPPED |  | No executable reference found |
| `var_overflow` | `INT` | — | — | — | UNMAPPED |  | diag_system |
| `Weighing_A_done` | `BOOL` | — | — | — | UNMAPPED | Internal bit for weighing material A done | Weighing_Material_A |
| `Weighing_B_done` | `BOOL` | — | — | — | UNMAPPED | Internal bit for weighing Material B done | Weighing_Material_B |
| `Weighing_Material_A` | `INT` | — | — | — | UNMAPPED | Weighing material A in progress | Weighing_Material_A, Weighing_Material_B |
| `Weighing_Material_B` | `INT` | — | — | — | UNMAPPED | Weighing material B in progress | Weighing_Material_B |
| `Weight_empty` | `EBOOL` | — | — | — | UNMAPPED | Weight empty | Weighing_Material_A |

## Robot member inventory

Robot_one is an ordinary application DDT of type Robot, not a device DDT. None of its members has a declared I/O address or hardware owner, and none is linked to a field-module DDT in the exported logic.

| Application field | Type | Meaning | I/O address or device field | Module | Channel | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `Robot_one.robot_running` | BOOL | Robot running | — | — | — | UNMAPPED — application state/command |
| `Robot_one.Rotation_left` | BOOL | Robot rotation left | — | — | — | UNMAPPED — application state/command |
| `Robot_one.Arm_one` | BOOL | Movement arm one | — | — | — | UNMAPPED — application state/command |
| `Robot_one.Arm_two` | BOOL | Movement arm two | — | — | — | UNMAPPED — application state/command |
| `Robot_one.Taking_Material` | BOOL | Taking up material | — | — | — | UNMAPPED — application state/command |
| `Robot_one.Rotation_right_five` | BOOL | Rotation right | — | — | — | UNMAPPED — application state/command |
| `Robot_one.Rotation_right_ten` | BOOL | Rotation right | — | — | — | UNMAPPED — application state/command |
| `Robot_one.Rotation_left_done` | BOOL | Robot rotation left done | — | — | — | UNMAPPED — application state/command |
| `Robot_one.Arm_one_done` | BOOL | Movement arm one done | — | — | — | UNMAPPED — application state/command |
| `Robot_one.Arm_two_done` | BOOL | Movement arm two done | — | — | — | UNMAPPED — application state/command |
| `Robot_one.packaging_5` | BOOL | Packaging 5 pices | — | — | — | UNMAPPED — application state/command |
| `Robot_one.packaging_10` | BOOL | Packaging 10 pices | — | — | — | UNMAPPED — application state/command |
| `Robot_one.rotation_right_five_done` | BOOL | Rotation right done | — | — | — | UNMAPPED — application state/command |
| `Robot_one.rotation_right_ten_done` | BOOL | Rotation right done | — | — | — | UNMAPPED — application state/command |
| `Robot_one.material_down` | BOOL | Material down in package | — | — | — | UNMAPPED — application state/command |
| `Robot_one.cvRobot_one` | BOOL | Internal variable robot | — | — | — | UNMAPPED — application state/command |
| `Robot_one.cvArm_one` | BOOL | Internal variable arm one | — | — | — | UNMAPPED — application state/command |
| `Robot_one.cvArm_two` | BOOL | Internal variable arm two | — | — | — | UNMAPPED — application state/command |
| `Robot_one.arm_right` | BOOL | Internal variable for movement arm right | — | — | — | UNMAPPED — application state/command |
| `Robot_one.cv_arm_right` | BOOL | Internal variable for movement arm right | — | — | — | UNMAPPED — application state/command |
| `Robot_one.cv_material_down_done` | BOOL | Internal variable for material down done | — | — | — | UNMAPPED — application state/command |
| `Robot_one.material_down_done` | BOOL | Material down in package done | — | — | — | UNMAPPED — application state/command |
| `Robot_one.init` | BOOL | Initialisation | — | — | — | UNMAPPED — application state/command |

## Important unmapped process signals

- Start, Stop, BP0, BP1 and SWITCH0 have no physical input assignment. Names and comments alone do not establish a push-button channel.
- Measured_temp has no analog input assignment; Heating increments/decrements it in application logic. No link to Analog_input_0–3 or AMI0410_0_7 was found.
- Valve_A_open/closed, Valve_B_open/closed, Conveying_screw, Forming, Belt_running, Material_picked_off and every Robot_one member have no field I/O mapping in this application.
- Sec, Ms_100 and Ms_10 are assigned from system bits %S6, %S5 and %S4 in Weighing_Material_A. These are system timebases, not physical input channels.
- Current_position at %MW10 and recipe at %MW100 have PLC memory locations only; neither location identifies a sensor, actuator, module or channel.

## Evidence and limits

- Sources: get_status, get_hardware, list_variables(max_results=1000), and a fresh export_project ZEF; unitpro.xef was parsed for global declarations, IOConf, application sections, subroutine, SFC actions and Robot member declarations.
- Hardware mapping evidence: variables/@topologicalAddress; device DDT Owner and ManagedKey attributes matched to IOConf/moduleATS/deviceDDT and module equipInfo. Slot 5, 6 and 7 module ownership was verified in both locations.
- get_hardware reported an EIO-bus drop-enumeration parameter error. The exported IOConf contains the six field modules listed above on the local rack; no remote field-module mapping is claimed.
- Device-DDT leaf names were verified against installed Schneider FFBLibset/v12.0/IO/IOEthernetRemote definitions for T_U_DIS_STD_IN_32, T_U_DIS_STD_CH_IN, T_U_DIS_STD_OUT_16, T_U_DIS_STD_CH_OUT, T_U_ANA_STD_IN_4, T_U_ANA_STD_CH_IN and T_U_ANA_VALUE_IN (type versions 1.10, with T_U_ANA_VALUE_IN version 1.00). These are installed library definitions; the full project export omits their type bodies.
- Analog_input_0–3 are T_ANA_IN_GEN channel structures located at %CH0.4.0–3. Their channel binding is established, but no unverified structure leaf name or process alias is asserted.
- Configured mapping does not establish terminal wiring or the presence of hardware on a running PLC. No PLC connection or live read/write was performed.
- Source STU SHA-256: `5243304e7c0289eb56b63359b4c2c8fd406ec39612dd513293abda3cb2e45538`.
