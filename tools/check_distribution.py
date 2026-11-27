"""Check release archives for missing modules and unintended local/vendor files."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import stat
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "control_expert_mcp"
HELPERS = {
    "check_distribution.py", "check_ce_automation.py", "export_ce_help.py",
    "requirements-help.txt", "test_export_ce_help.py", "test_mcp_runtime.py",
    "index_ce_help.py", "test_documentation.py", "test_diagnostics.py", "test_project_open.py",
    "test_project_export.py",
    "test_benchmark.py", "benchmark_fake_server.py",
    "test_benchmark_archive.py", "test_benchmark_alarms.py",
    "test_opc.py", "check_opc.py",
    "check_simulator.py",
    "test_opc_benchmark.py",
    "test_simulator_benchmark.py",
    "test_iec_benchmark.py",
}


def safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"Unsafe archive path: {name}")
    return path


def check_wheel(path: Path, expected_modules: set[str]) -> None:
    with zipfile.ZipFile(path) as archive:
        files = []
        metadata_roots = set()
        for entry in archive.infolist():
            relative = safe_path(entry.filename)
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError(f"Symlink in wheel: {entry.filename}")
            if entry.is_dir():
                continue
            if relative.parts[0].endswith(".dist-info"):
                metadata_roots.add(relative.parts[0])
            elif relative.as_posix() not in expected_modules:
                raise ValueError(f"Unexpected wheel content: {entry.filename}")
            files.append(relative.as_posix())
        missing = expected_modules - set(files)
        if missing:
            raise ValueError(f"Missing wheel modules: {sorted(missing)}")
        if len(metadata_roots) != 1:
            raise ValueError("Expected exactly one wheel metadata directory")
        metadata_root = next(iter(metadata_roots))
        entry_points = archive.read(f"{metadata_root}/entry_points.txt").decode("utf-8")
        if "control-expert-mcp = control_expert_mcp.server:main" not in entry_points:
            raise ValueError("Missing MCP console entry point")
    print(f"OK {path.name}: {len(files)} files, all runtime modules and console entry point present")


def check_sdist(path: Path, expected_modules: set[str]) -> None:
    source_modules = {"src/" + name for name in expected_modules}
    allowed = source_modules | {
        "README.md", "README.it.md", "docs/guide.md", "pyproject.toml", "MANIFEST.in", "PKG-INFO", "setup.cfg", "LICENSE",
        "benchmarks/example.json", "benchmarks/README.md", "benchmarks/CHECKPOINT.md",
        "benchmarks/deepseek.example.json",
        "benchmarks/opc.example.json", "tools/lang_refs/OPC_Bench.xml",
        "benchmarks/simulator.example.json",
        "benchmarks/iec.example.json", "docs/Benchmark_IEC_Implementation.md",
        "tools/lang_refs/ST_2_Feeder.xml",
        *("tools/" + name for name in HELPERS),
        *(p.relative_to(ROOT).as_posix() for p in (ROOT / "samples").glob("*.json")),
    }
    files = set()
    roots = set()
    with tarfile.open(path, "r:gz") as archive:
        for entry in archive.getmembers():
            relative = safe_path(entry.name)
            roots.add(relative.parts[0])
            if entry.isdir():
                continue
            if not entry.isfile():
                raise ValueError(f"Non-regular source archive member: {entry.name}")
            name = PurePosixPath(*relative.parts[1:]).as_posix()
            if name not in allowed and not name.startswith(f"src/{PACKAGE}.egg-info/"):
                raise ValueError(f"Unexpected source archive content: {entry.name}")
            files.add(name)
    missing = (source_modules | {"README.md", "pyproject.toml", "MANIFEST.in"}) - files
    if missing or len(roots) != 1:
        raise ValueError(f"Invalid source archive: roots={sorted(roots)}, missing={sorted(missing)}")
    print(f"OK {path.name}: {len(files)} files; local manuals, scratch data, and vendor extracts excluded")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    expected = {f"{PACKAGE}/{p.relative_to(ROOT / 'src' / PACKAGE).as_posix()}"
                for p in (ROOT / "src" / PACKAGE).rglob("*.py")}
    wheels = list(args.dist_dir.glob("*.whl"))
    sources = list(args.dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        parser.error("Expected exactly one wheel and one .tar.gz in --dist-dir; use a fresh build directory")
    try:
        check_wheel(wheels[0], expected)
        check_sdist(sources[0], expected)
    except (ValueError, KeyError, tarfile.TarError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Distribution check failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
