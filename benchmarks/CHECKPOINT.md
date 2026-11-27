# Current benchmark rubrics

| Rubric | Accepts |
| --- | --- |
| `feeder-3` | Inspection facts all correct; one whole-answer Markdown fence tolerated |
| `feeder-temperature-2` | Recognized inclusive ±2.0 predicates, redundant bound parentheses allowed |
| `feeder-alarms-2` | Alarm hysteresis proven over all INT; `SET`/`RESET` on fault flags allowed |
| `demo-weighing-1` | Both weighing identifiers named |
| `demo-io-mapping-6` | All 29 checks: 11 physical, 2 internal-memory, 14 unmapped signals, Robot_one |
| `simulator-counter-1` | Independently sampled `TEST_LLM` +1 per second |
| `opc-live-1` | Independent OPC reads match written inputs and outputs |
| `iec-native-trace-1` | Captured IEC traces match the reference |

Validation:

```powershell
python -m unittest discover -s tools -p "test_*.py" -v
python -m compileall -q src
```
