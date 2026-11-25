"""IEC correctness summaries and standalone progress graphics."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .core import digest, read_json, write_json
from .iec_cases import CASES
from .iec_grade import VERDICTS


def summarize(rows: list[dict]) -> dict:
    scores = [r.get("validation", r) for r in rows]
    started = [r.get("validation", r) for r in rows if r.get("status") != "not_started"]
    verified = [v for v in scores if v.get("correctness_percent") is not None]
    total = sum(v["evaluated_outputs"] for v in verified)
    matched = sum(v["matched_outputs"] for v in verified)
    return {"attempts": len(rows), "verified_attempts": len(verified),
            "started_attempts": len(started), "not_started": len(rows) - len(started),
            "unverified_attempts": len(rows) - len(verified),
            "passed": sum(v.get("verdict") == "pass" for v in scores),
            "verdicts": dict(Counter(v.get("verdict", "infrastructure_error") for v in started)),
            "correctness_percent": 100 * matched / total if total else None,
            "case_mean_correctness_percent": (sum(v["correctness_percent"] for v in verified) / len(verified)
                                               if verified else None),
            "matched_outputs": matched, "evaluated_outputs": total}


def write_report(directory: Path, rows: list[dict]) -> dict:
    summary = summarize(rows)
    report = {"suite": "iec", "summary": summary, "cases": rows,
              "score_definition": "100 * matched evaluated output cells / all evaluated output cells, valid captures only",
              "limitations": "Unverified attempts have unknown correctness, never 0%. Strict pass requires every check."}
    write_json(directory / "iec-report.json", report)
    lines = ["# IEC benchmark", "", report["score_definition"], "", report["limitations"], "",
             "| Case | Condition | Evidence | Verdict | Correctness | Matched/evaluated |",
             "|---|---|---|---|---:|---:|"]
    for row in rows:
        v = row["validation"]
        percent = v.get("correctness_percent")
        score = "unverified" if percent is None else f"{percent:.2f}%"
        lines.append(f"| {row['task']} | {row['condition']} | {row.get('variant', 'model')} | {v['verdict']} | "
                     f"{score} | {v.get('matched_outputs')}/{v.get('evaluated_outputs', 0)} |")
    lines += ["", f"Verified attempts: {summary['verified_attempts']}/{summary['attempts']}.",
              "Micro correctness weights each output cell; case mean weights each verified attempt equally."]
    (directory / "iec-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def overview(results: Path, output: Path) -> dict:
    """Group by run/condition/evidence kind; never pool different fingerprints."""
    groups = defaultdict(list)
    identities = {}
    plans = sorted(results.glob("*/plan.json"))
    if (results / "plan.json").is_file():
        plans = [results / "plan.json"]
    for plan_path in plans:
        plan = read_json(plan_path)
        if plan.get("snapshot", {}).get("suite") != "iec":
            continue
        for item in plan["schedule"]:
            attempts = sorted((plan_path.parent / item["case_id"]).glob("attempt-*/summary.json"))
            if attempts:
                row = read_json(attempts[-1])
                if row.get("fingerprint") != plan["fingerprint"]:
                    raise ValueError("IEC summary fingerprint mismatch")
            else:
                # Missing attempts remain visible as unverified infrastructure.
                row = {**item, "status": "not_started", "validation": {"correctness_percent": None}}
            key = (plan["run_id"], item["condition"], item.get("variant", "model"), plan["fingerprint"])
            config = plan.get("snapshot", {}).get("config", {})
            identities[key] = {"requested_model": (row.get("requested_model") or config.get("model", {}).get("id", "unknown"))
                               if key[2] == "model" else "scripted",
                               "provider": config.get("provider", {}).get("name"), "mode": plan.get("mode")}
            groups[key].append(row)
    if not groups:
        raise ValueError("No IEC campaigns found")
    from matplotlib import pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable
    from matplotlib.ticker import MaxNLocator
    labels = list(CASES)
    count = len(groups)
    fig, (left, right) = plt.subplots(1, 2, figsize=(15, max(3.8, count * .7 + 1.9)),
                                    gridspec_kw={"width_ratios": [1.6, 1]}, layout="constrained")
    cmap = plt.get_cmap("RdYlGn")
    norm = Normalize(0, 100)
    metadata = []
    colors = {"pass": "#2e7d32", "output_mismatch": "#e5a832", "artifact_invalid": "#cf5353",
              "build_failed": "#965da6", "infrastructure_error": "#8a949e", "unsupported_authoring": "#546e7a"}
    for y, (key, rows) in enumerate(groups.items()):
        run_id, condition, variant, fingerprint = key
        per_case = {case: summarize([r for r in rows if r["task"] == case]) for case in labels}
        for x, case in enumerate(labels):
            stats = per_case[case]
            percent = stats["correctness_percent"]
            face = "#e6e9ed" if percent is None else cmap(norm(percent))
            left.add_patch(plt.Rectangle((x - .48, y - .44), .96, .88, facecolor=face))
            text = "—" if percent is None else f"{percent:.1f}%"
            text += f"\n{stats['verified_attempts']}/{stats['attempts']} verified"
            left.text(x, y, text, ha="center", va="center", fontsize=8)
        stats = summarize(rows)
        start = 0
        for verdict in VERDICTS:
            n = stats["verdicts"].get(verdict, 0)
            right.barh(y, n, left=start, color=colors[verdict], label=verdict if y == 0 else None)
            start += n
        if stats["not_started"]:
            right.barh(y, stats["not_started"], left=start, color="#e6e9ed", hatch="//",
                       label="not_executed" if y == 0 else None)
        metadata.append({"run_id": run_id, "condition": condition, "variant": variant,
                         "fingerprint": fingerprint, **identities[key], "summary": stats, "cases": per_case})
    left.set_xlim(-.5, len(labels) - .5)
    left.set_ylim(count - .5, -.5)
    left.set_xticks(range(len(labels)), [CASES[c].language for c in labels])
    left.set_yticks(range(count), [f"{k[0]}\n{k[1]} · {k[2]} · {identities[k]['requested_model']}\n{k[3][:8]}" for k in groups], fontsize=8)
    left.set_title("Correct output cells (%) · unknown shown in gray")
    right.set_ylim(count - .5, -.5)
    right.set_yticks([])
    right.set_xlabel("Scheduled slots (including unverified)")
    right.xaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=2))
    right.set_title("Strict verdicts")
    fig.legend(*right.get_legend_handles_labels(), loc="outside lower center", ncol=4, fontsize=8)
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=left, shrink=.6, label="Correctness %")
    fig.suptitle("IEC 61131-3 benchmark · correctness and strict acceptance")
    output = output.with_suffix(".png")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    fig.savefig(output.with_suffix(".svg"))
    plt.close(fig)
    report = {"suite": "iec", "groups": metadata, "generator_sha256": digest(Path(__file__).read_bytes()),
              "score_definition": "Output-cell correctness over valid captures only; denominator coverage is displayed."}
    write_json(output.with_suffix(".json"), report)
    return report
