# Current benchmark grader

I/O mapping uses `demo-io-mapping-4` in
`src/control_expert_mcp/benchmark/mapping_grade.py`.

The grader checks 11 physical mappings, two internal-memory locations,
14 representative unmapped process signals, and Robot_one. Acceptance requires
all 29 checks. Results distinguish matched, missing, and incorrect facts.

Supported tables include grouped signals, singular or plural signal headings,
`Signal(s)`, module spacing, direction/channel labels, and spelled-out channel
counts. Device counts must match module direction. A separate hardware table
can establish device-DDT channels through an explicit slot/module join.
Contradictory mappings and omitted required signals fail.

The mapping prompt requests complete signal coverage and separates hardware
ownership from application use. Regrading saved replies makes no provider or
Control Expert calls. Current scoring results and graphics are in
[archive](archive/README.md). The overview displays I/O correctness as matched
checks divided by required checks, with separate pass counts.

Validation: `python -m unittest discover -s tools -p "test_*.py" -v` and
`python -m compileall -q src`.
