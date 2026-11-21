"""Static graphical overview generated exclusively from sanitized archive records."""
from __future__ import annotations

import copy
from importlib.metadata import version
from pathlib import Path
import re

from .core import digest, read_json, write_json
from .report import aggregate


def chart_rows(archive: Path, scoring: str = "latest") -> tuple[list, dict]:
    """Keep campaigns separate; never pool incompatible experiments or models."""
    rows, inputs = [], {}
    for path in sorted(archive.glob("*/record.json")):
        if path.parent.name.startswith("."):
            continue
        record = read_json(path)
        checksums = read_json(path.parent / "checksums.json")
        if digest(path.read_bytes()) != checksums["record.json"]:
            raise ValueError("Archive record checksum mismatch")
        inputs[path.relative_to(archive).as_posix()] = digest(path.read_bytes())
        grades = record.get("inspection_regrades", []) if scoring == "latest" else []
        def key(grade):
            return [int(n) for n in re.findall(r"\d+", grade["rubric"])]
        grades = sorted(grades, key=key)
        cases = copy.deepcopy(record["cases"])
        for grade in grades:
            for case in cases:
                if (case["case_id"], case["attempt_id"]) == (grade["case_id"], grade["attempt_id"]):
                    case.update(success=grade["success"], validation=grade["validation"])
        for condition in sorted({case["condition"] for case in cases}):
            selected = [case for case in cases if case["condition"] == condition]
            server = record["servers"][condition]
            source = server.get("verified_source_commit") or server.get("source", {}).get("revision") or "unknown"
            actual_rubrics = sorted({case["validation"]["rubric"] for case in selected if case.get("validation", {}).get("rubric")})
            rows.append({"run_id": record["run_id"], "model": record["model"]["id"], "provider": record["provider"],
                "model_identity": record["model"].get("identity", "pinned"), "source": source, "condition": condition,
                "scoring": ", ".join(actual_rubrics) or record["rubric_version"],
                "original": record["conditions"][condition]["overall"], "overall": aggregate(selected),
                "tasks": {task: aggregate([case for case in selected if case["task"] == task])
                          for task in sorted({case["task"] for case in selected})}})
    return rows, inputs


def visualize_archive(archive: Path, output: Path, scoring: str = "latest") -> Path:
    if scoring not in {"original", "latest"}:
        raise ValueError("Scoring must be original or latest")
    rows, inputs = chart_rows(archive, scoring)
    if not rows:
        raise ValueError("Archive has no records")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    preferred = ["inspect", "threshold", "temperature", "repair", "alarms"]
    task_names = {task for row in rows for task in row["tasks"]}
    tasks = [task for task in preferred if task in task_names] + sorted(task_names - set(preferred))
    height = 5.2 + .85 * len(rows)
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 12,
                         "figure.facecolor": "#f6f8fc", "axes.facecolor": "white"}):
        fig = plt.figure(figsize=(17, height), dpi=150)
        grid = fig.add_gridspec(2, 3, height_ratios=[max(2, .68 * len(rows)), 1.65],
                               left=.31, right=.97, top=.74, bottom=.19, hspace=.85, wspace=.3)
        labels = [f"{row['provider']} / {row['model']}\n{row['source'][:12]} · {row['condition']}\n"
                  + row['scoring'].replace('feeder-temperature-', 'temperature-').replace('feeder-alarms-', 'alarms-')
                  for row in rows]
        specs = [("Accepted / attempts", "RdYlGn", "acceptance"),
                 ("Median workflow · seconds", "Blues", "time"),
                 ("Median provider tokens · thousands", "Purples", "tokens")]
        for index, (title, cmap, kind) in enumerate(specs):
            axis = fig.add_subplot(grid[0, index])
            values = np.full((len(rows), len(tasks)), np.nan)
            texts = [["—"] * len(tasks) for _ in rows]
            for y, row in enumerate(rows):
                for x, task in enumerate(tasks):
                    data = row["tasks"].get(task)
                    if not data:
                        continue
                    if kind == "acceptance":
                        values[y, x] = data["accepted"]["rate_all"]
                        texts[y][x] = f"{data['accepted']['pass']}/{data['cases']}"
                    else:
                        measure = data["all_attempts"]["workflow_seconds" if kind == "time" else "total_tokens"]
                        val = measure["median"]
                        if val is not None:
                            values[y, x] = val / (1000 if kind == "tokens" else 1)
                            texts[y][x] = f"{values[y, x]:.1f}" + ("*" if measure["unknown_n"] else "")
            maximum = 1 if kind == "acceptance" else max(1, float(np.nanmax(values)) if np.any(~np.isnan(values)) else 1)
            axis.imshow(values, aspect="auto", cmap=cmap, vmin=0, vmax=maximum)
            axis.set_xticks(range(len(tasks)), [task.title() for task in tasks], rotation=25, ha="right")
            axis.set_yticks(range(len(rows)), labels if index == 0 else [""] * len(rows))
            axis.tick_params(length=0, pad=10)
            axis.set_title(title, loc="left", pad=16, fontweight="bold")
            axis.set_xticks(np.arange(-.5, len(tasks), 1), minor=True)
            axis.set_yticks(np.arange(-.5, len(rows), 1), minor=True)
            axis.grid(which="minor", color="white", linewidth=3)
            axis.tick_params(which="minor", length=0)
            for y in range(len(rows)):
                for x in range(len(tasks)):
                    color = "white" if not np.isnan(values[y, x]) and values[y, x] > (.8 if kind == "acceptance" else .6 * maximum) else "#172033"
                    axis.text(x, y, texts[y][x], ha="center", va="center", color=color, fontweight="bold", fontsize=11)
            for spine in axis.spines.values():
                spine.set_visible(False)
        table_axis = fig.add_subplot(grid[1, :])
        table_axis.axis("off")
        table = []
        for row in rows:
            overall = row["overall"]
            original = row["original"]["accepted"]["pass"]
            active = overall["accepted"]["pass"]
            table.append([row["condition"] + " · " + row["run_id"][:15], f"{original} → {active} / {overall['cases']}",
                          f"{overall['build']['pass']}/{overall['build']['n']}", str(overall["tool_errors"]),
                          f"{overall['all_attempts']['total_tokens']['known_n']}/{overall['cases']}"])
        artist = table_axis.table(cellText=table, colLabels=["Condition / campaign", "Accepted: original → view", "Builds: pass / edits", "Tool errors", "Known token samples"],
                                  loc="center", cellLoc="center", colWidths=[.3, .25, .2, .1, .15])
        artist.auto_set_font_size(False)
        artist.set_fontsize(9)
        artist.scale(1, 1.7)
        for (r, _), cell in artist.get_celld().items():
            cell.set_edgecolor("#dfe5ef")
            cell.set_facecolor("#e7edf6" if r == 0 else "white")
        models = len({(r["provider"], r["model"]) for r in rows})
        revisions = len({r["source"] for r in rows})
        runs = len(inputs)
        fig.text(.045, .945, "Control Expert · benchmark archive", fontsize=24, fontweight="bold", color="#172033")
        fig.text(.045, .885, f"{runs} campaign(s) · {models} model(s) · {revisions} measured source revision(s) · scoring view: {scoring}", fontsize=12, color="#4b5870")
        fig.text(.045, .825, "A: reference tools only     B: installed manuals available     |     Campaigns remain separate; no incompatible pooling.", fontsize=10, color="#4b5870")
        fig.text(.045, .085, "Counts show sample sizes. Time excludes setup/evaluation; tokens are provider totals across all requests. * = some usage unknown.", fontsize=9, color="#4b5870")
        fig.text(.045, .045, "Smoke-test evidence, not a significance claim. Mutable model aliases limit reproducibility. PLC runtime behavior remains unverified.", fontsize=9, color="#4b5870")
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, facecolor=fig.get_facecolor(), metadata={"Software": "ce-bench"})
        plt.close(fig)
    write_json(output.with_suffix(".metadata.json"), {"plot_version": 1, "scoring_view": scoring,
        "inputs": inputs, "image_sha256": digest(output.read_bytes()), "generator_sha256": digest(Path(__file__).read_bytes()),
        "matplotlib": version("matplotlib"), "rows": rows})
    return output
