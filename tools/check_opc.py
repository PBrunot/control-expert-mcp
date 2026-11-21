"""Inspect OFS; optionally exercise/restore the supplied M580 demo temperature input.

Requires explicit live permission flags. Never downloads, builds, starts/stops a
PLC, or opens a UDE project. Use --exercise-demo only with the known demo running
on a simulator or supervised test bench.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alias', required=True, help='User-confirmed OFS device alias')
    parser.add_argument('--allow-live', action='store_true', help='User permits live OPC connections')
    parser.add_argument('--confirm-ofs-running', action='store_true', help='User confirms OFS is available/running')
    parser.add_argument('--exercise-demo', action='store_true', help='User approves reversible closed-loop demo tests')
    parser.add_argument('--report', type=Path, help='Local JSON evidence destination; do not commit raw exports')
    args = parser.parse_args()
    if not args.allow_live or not args.confirm_ofs_running:
        parser.error('Explicit --allow-live and --confirm-ofs-running are required')

    from control_expert_mcp import server as s
    if not s.ONLINE_ENABLED:
        parser.error('Set CE_MCP_ENABLE_ONLINE=1 before running live validation')

    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
              'project_prerequisite': 'samples/demo_ControlExpert_M580.STU' if args.exercise_demo else None}
    original = {}
    tags = ['Measured_temp', 'Cmeasured_temp', 'Setpoint_temp', 'Temp_ok',
            'Start', 'Sec', 'Forming_motor.running_left']
    try:
        report['setup'] = s.configure_live_access(True, 'opc', args.alias, True, args.exercise_demo)
        report['connect'] = s.opc_connect()
        report['root'] = s.opc_browse()
        report['device'] = s.opc_browse([args.alias])
        if args.exercise_demo:
            report['dfb'] = s.opc_browse([args.alias, 'Forming_motor'])
            report['before'] = s.opc_read_tags(tags)
            if report['before']['errors']:
                raise RuntimeError(str(report['before']['errors']))
            original = {'Measured_temp': report['before']['values']['Measured_temp']}
            value = original['Measured_temp'] + 1
            report['write'] = s.opc_write_tags({'Measured_temp': value})
            if report['write']['errors']:
                raise RuntimeError(str(report['write']['errors']))
            deadline = time.monotonic() + 5
            while True:
                report['after'] = s.opc_read_tags(tags)
                if (report['after']['values'].get('Measured_temp') == value and
                        report['after']['values'].get('Cmeasured_temp') == float(value)):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('PLC derived output did not follow the test input')
                time.sleep(.1)
        report['success'] = True
    except Exception as exc:
        report['success'] = False
        report['error'] = str(exc)
    finally:
        if original:
            try:
                report['restore'] = s.opc_write_tags(original)
                time.sleep(.2)
                report['restored_values'] = s.opc_read_tags(tags)
                if (report['restore']['errors'] or
                        report['restored_values']['values'].get('Measured_temp') != original['Measured_temp'] or
                        report['restored_values']['values'].get('Cmeasured_temp') != float(original['Measured_temp'])):
                    raise RuntimeError('Demo input/output restoration could not be verified')
            except Exception as exc:
                report['success'] = False
                report['restore_error'] = str(exc)
        report['disconnect'] = s.opc_disconnect()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
