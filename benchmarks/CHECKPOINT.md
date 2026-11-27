# Current benchmark grader

I/O mapping uses `demo-io-mapping-6` in
`src/control_expert_mcp/benchmark/mapping_grade.py`.

The grader checks 11 physical mappings, two internal-memory locations,
14 representative unmapped process signals, and Robot_one. Acceptance requires
all 29 checks. Results distinguish matched, missing, and incorrect facts.

Supported tables include grouped signals, singular or plural signal headings,
`Signal(s)`, module spacing, direction/channel labels, and spelled-out channel
counts. Device counts must match module direction. A separate hardware table
can establish device-DDT channels through an explicit slot/module join.
Contradictory mappings and omitted required signals fail.

Rubric 6 also preserves unmapped parent headings across nested subsections,
reads explicit backtick identifier lists and repeated Signal/Type/Use columns,
resolves `same` only in the module column of the same table, and accepts discrete
channel counts, Unicode ranges and group/bit labels. Slot and module numbers are
not channel counts. Sibling or explicitly mapped subsections end unmapped scope.
Regression checks retain failures for missing signals, wrong channels, capacity,
direction, addresses and contradictory physical assignments.

All eight saved I/O answers across four campaigns were regraded with rubric 6.
Both DeepSeek campaigns and GPT-5.5 match 29/29 in each condition; GPT-6 Luna
remains at 23/29 (A) and 22/29 (B). Latest DeepSeek is 15/15 including the
independently verified simulator counter. Originals and earlier scoring remain
immutable. Each rubric family has its own archive snapshot; the overview takes
case evidence from one snapshot per run and applies the newest regrade of every
family (`feeder-`, `feeder-alarms-`, `demo-io-mapping-`) from all snapshots.
Fields that a newer archiver only adds (previously empty) are not treated as
changed evidence; any changed value still stops the overview.

`feeder-3` (inspection) accepts exactly one whole-answer Markdown fence around
the JSON; prose before or after still fails. The prompt still forbids fences,
so the original strict score remains in every archive. `feeder-alarms-2` treats
`SET(flag);`/`RESET(flag);` on the two fault flags as TRUE/FALSE assignments
(EBOOL edge history is not graded) and still proves every INT partition.
`ce-bench regrade --task alarms` re-proves saved `saved-section.xml` artifacts
offline, retaining the original build/save/declaration evidence. All offline
runs in `results/` were regraded with both rubrics on 2026-11-27; repair
failures (`int_to_real(0)`) remain correctly rejected.

The mapping prompt requests complete signal coverage and separates hardware
ownership from application use. Regrading saved replies makes no provider or
Control Expert calls. Current scoring results and graphics are in
[archive](archive/README.md). The overview displays I/O correctness as matched
checks divided by required checks, with separate pass counts.

Validation: `python -m unittest discover -s tools -p "test_*.py" -v` and
`python -m compileall -q src`.
