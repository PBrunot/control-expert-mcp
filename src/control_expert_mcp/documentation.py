"""Explicit local manual indexing and COM-independent, read-only retrieval."""

from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile


INDEX_NAME = "ce-help.sqlite3"
INDEX_VERSION = 1
LANGUAGES = {
    "en": {"1033", "eng", "en-us"}, "it": {"1040", "ita", "it-it"},
    "de": {"1031", "ger", "de-de"}, "fr": {"1036", "fre", "fr-fr"},
    "es": {"1034", "spa", "es-es"}, "zh": {"2052", "chi", "zh-cn"},
}


def corpus_directory() -> Path:
    """Resolve the configured corpus; packaged installations should set the env var."""
    return Path(os.environ.get("CE_MCP_MANUALS_DIR") or
                Path(__file__).resolve().parents[2] / "manuals" / "ce-16.4").resolve()


def _contained(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.drive or ".." in candidate.parts:
        raise ValueError(f"Unsafe manual path: {relative}")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Manual path escapes corpus: {relative}")
    return resolved


def _manifest(root: Path) -> tuple[dict, str]:
    path = _contained(root, "manifest.json")
    if not path.is_file():
        raise ValueError("Manual manifest missing. Run tools/export_ce_help.py first; "
                         "set CE_MCP_MANUALS_DIR to its output directory.")
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get("manuals"), list):
        raise ValueError("Invalid manual manifest: expected a manuals list.")
    return value, hashlib.sha256(raw).hexdigest()


def _plain(text: str) -> str:
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"\\([\\`*_{}\[\]()#+.!>-])", r"\1", text)
    return html.unescape(text)


def _sections(markdown: str):
    """Yield heading sections without splitting tables or fenced examples."""
    start, heading, anchor, page = 0, "", None, None
    fence = None
    pending_anchor = None
    pending_start = None
    offset = 0
    for line in markdown.splitlines(keepends=True):
        stripped = line.lstrip()
        marker = re.match(r"(`{3,}|~{3,})", stripped)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        if fence is None and not marker:
            found = re.search(r'<a\s+(?:id|name)=["\']([^"\']+)["\']', line, re.I)
            if found:
                pending_anchor, pending_start = found[1], offset
            title = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
            if title:
                boundary = pending_start if pending_start is not None else offset
                if boundary > start:
                    yield start, boundary, heading, anchor, page
                start, heading = boundary, _plain(title[1]).strip()
                anchor = pending_anchor
                match = re.fullmatch(r"Page\s+(\d+)", heading, re.I)
                if match:
                    page = int(match[1])
                pending_anchor, pending_start = None, None
            elif stripped.strip() and not found:
                pending_anchor, pending_start = None, None
        offset += len(line)
    if offset > start:
        yield start, offset, heading, anchor, page


def _chunks(markdown: str, start: int, end: int, target: int = 6000):
    """Bound search passages at paragraph boundaries, preserving fenced code/tables."""
    boundary, offset, fence = start, start, None
    for line in markdown[start:end].splitlines(keepends=True):
        marker = re.match(r"\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        offset += len(line)
        if not line.strip() and fence is None and offset - boundary >= target:
            yield boundary, offset
            boundary = offset
    if boundary < end:
        yield boundary, end


def build_index(directory: Path) -> dict:
    """Build a complete snapshot, then atomically replace the published index."""
    root = directory.resolve()
    manifest, fingerprint = _manifest(root)
    installation = manifest.get("installation")
    match = re.search(r"Control Expert\s+(\d+(?:\.\d+)+)", installation or "", re.I)
    installation_version = manifest.get("installation_version") or (match[1] if match else None)
    fd, filename = tempfile.mkstemp(prefix=".ce-help-", suffix=".sqlite3", dir=root)
    os.close(fd)
    temporary = Path(filename)
    counts = {"manuals": 0, "topics": 0, "sections": 0, "chunks": 0}
    try:
        with closing(sqlite3.connect(temporary)) as db, db:
            db.executescript("""
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE topics (id TEXT PRIMARY KEY, title TEXT, markdown TEXT,
                                     citation TEXT, language TEXT, library TEXT,
                                     manual_version TEXT);
                CREATE TABLE sections (topic_id TEXT, start INTEGER, end INTEGER,
                                       heading TEXT, anchor TEXT, page INTEGER);
                CREATE TABLE chunks (section_id INTEGER, start INTEGER, end INTEGER);
                CREATE VIRTUAL TABLE search USING fts5(title, heading, body,
                    tokenize="unicode61 tokenchars '_'");
            """)
            seen = set()
            for manual in manifest["manuals"]:
                if manual.get("status") not in {"converted", "cached"}:
                    continue
                folder = _contained(root, manual["folder"])
                source = manual["source"]
                language = manual.get("language") or next(
                    (key for key, names in LANGUAGES.items()
                     if set(re.split(r"[/\\]", source.lower())) & names), None)
                counts["manuals"] += 1
                for output in manual["outputs"]:
                    if Path(output).suffix.lower() != ".md":
                        continue
                    path = _contained(folder, output)
                    if not path.is_relative_to(root):
                        raise ValueError("Manual topic escapes corpus")
                    relative = path.relative_to(root).as_posix()
                    identity = source + "\n" + Path(output).as_posix()
                    topic_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
                    if topic_id in seen:
                        raise ValueError(f"Duplicate manual topic: {identity}")
                    seen.add(topic_id)
                    markdown = path.read_text(encoding="utf-8")
                    sections = list(_sections(markdown))
                    title = next((s[2] for s in sections if s[2]), path.stem)
                    citation = {
                        "book_title": manual.get("title"), "source_path": source,
                        "source_sha256": manual.get("fingerprint", {}).get("source_sha256"),
                        "converter_fingerprint": manual.get("fingerprint", {}).get("converter"),
                        "topic_path": relative, "topic_id": topic_id,
                        "source_topic_path": Path(output).as_posix(),
                        "topic_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
                        "installation": installation, "installation_version": installation_version,
                        "manual_version": manual.get("manual_version"),
                        "document_revision": manual.get("document_revision"),
                        "language": language, "library": manual.get("library"),
                        "warnings": manual.get("warnings", []),
                    }
                    db.execute("INSERT INTO topics VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (topic_id, title, markdown, json.dumps(citation), language,
                                manual.get("library"), manual.get("manual_version")))
                    for start, end, heading, anchor, page in sections:
                        cursor = db.execute("INSERT INTO sections VALUES (?, ?, ?, ?, ?, ?)",
                                            (topic_id, start, end, heading, anchor, page))
                        for chunk_start, chunk_end in _chunks(markdown, start, end):
                            body = _plain(markdown[chunk_start:chunk_end])
                            if not body.strip():
                                continue
                            chunk = db.execute("INSERT INTO chunks VALUES (?, ?, ?)",
                                               (cursor.lastrowid, chunk_start, chunk_end))
                            db.execute("INSERT INTO search(rowid, title, heading, body) VALUES (?, ?, ?, ?)",
                                       (chunk.lastrowid, _plain(title), _plain(heading),
                                        body))
                            counts["chunks"] += 1
                    counts["topics"] += 1
                    counts["sections"] += len(sections)
            # Detect a published manifest change during indexing.
            if _manifest(root)[1] != fingerprint:
                raise ValueError("Manifest changed during indexing; rerun the indexer.")
            metadata = {"index_version": INDEX_VERSION, "manifest_sha256": fingerprint,
                        "indexed_at": datetime.now(timezone.utc).isoformat(),
                        "installation": installation, "installation_version": installation_version,
                        "counts": counts,
                        "failures": [m for m in manifest["manuals"]
                                     if m.get("status") not in {"converted", "cached"}],
                        "warnings": [{"source": m["source"], "warnings": m["warnings"]}
                                     for m in manifest["manuals"] if m.get("warnings")]}
            db.executemany("INSERT INTO metadata VALUES (?, ?)",
                           [(key, json.dumps(value)) for key, value in metadata.items()])
            db.execute("INSERT INTO search(search) VALUES ('optimize')")
        os.replace(temporary, _contained(root, INDEX_NAME))
    finally:
        temporary.unlink(missing_ok=True)
    return metadata


@contextmanager
def _reader(directory: Path):
    path = _contained(directory, INDEX_NAME)
    if not path.is_file():
        raise ValueError("Manual index missing. Run tools/index_ce_help.py --manuals-dir "
                         "<corpus> after conversion. Indexing never runs inside MCP requests.")
    try:
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        try:
            metadata = {row[0]: json.loads(row[1]) for row in db.execute("SELECT * FROM metadata")}
            if metadata.get("index_version") != INDEX_VERSION:
                raise ValueError("Unsupported manual index version; rebuild with tools/index_ce_help.py.")
            yield db, metadata
        finally:
            db.close()
    except sqlite3.Error as exc:
        raise ValueError(f"Manual index could not be read; rebuild with tools/index_ce_help.py: {exc}") from None


def _freshness(directory: Path, metadata: dict) -> str:
    return "current" if _manifest(directory)[1] == metadata["manifest_sha256"] else "stale"


def documentation_status(directory: Path | None = None) -> dict:
    """Describe conversion/index health without creating files or opening COM."""
    root = directory or corpus_directory()
    result = {"corpus_directory": str(root), "ready": False}
    try:
        manifest, _ = _manifest(root)
        result.update(manifest_sources=len(manifest["manuals"]),
                      conversion_failures=[m for m in manifest["manuals"]
                                           if m.get("status") not in {"converted", "cached"}],
                      conversion_warnings=[{"source": m["source"], "warnings": m["warnings"]}
                                           for m in manifest["manuals"] if m.get("warnings")])
        with _reader(root) as (_, metadata):
            freshness = _freshness(root, metadata)
            result.update(metadata, freshness=freshness, ready=freshness == "current")
    except (ValueError, OSError) as exc:
        result["error"] = str(exc)
    return result


def _require_current(root: Path, metadata: dict) -> None:
    if _freshness(root, metadata) != "current":
        raise ValueError("Manual index is stale; rerun tools/index_ce_help.py before retrieval.")


def _citation(row, heading=None, anchor=None, page=None) -> dict:
    return {**json.loads(row["citation"]), "heading": heading, "anchor": anchor, "page": page}


def search_manuals(query: str, library: str = "", language: str = "", limit: int = 8,
                   manual_version: str = "", installation_version: str = "",
                   directory: Path | None = None) -> dict:
    """Search literal terms, prioritizing exact titles/symbols over full-text rank."""
    if not 1 <= limit <= 50 or not 1 <= len(query.strip()) <= 512:
        raise ValueError("Use a nonempty query of at most 512 characters and limit 1..50.")
    words = re.findall(r"\w+", _plain(query), re.UNICODE)
    if not words:
        raise ValueError("Query must contain a word or IEC symbol.")
    expression = " OR ".join('"' + word + '"' for word in words[:40])
    root = directory or corpus_directory()
    with _reader(root) as (db, metadata):
        _require_current(root, metadata)
        if installation_version and installation_version != metadata.get("installation_version"):
            return {"results": [], "freshness": "current"}
        rows = db.execute("""
            SELECT t.id, t.title, t.citation, c.start, c.end, s.heading, s.anchor, s.page,
                   snippet(search, 2, '', '', ' … ', 48) AS excerpt
            FROM search JOIN chunks c ON c.rowid=search.rowid
            JOIN sections s ON s.rowid=c.section_id
            JOIN topics t ON t.id=s.topic_id
            WHERE search MATCH ? AND (?='' OR t.library=? OR instr(lower(json_extract(t.citation,
                  '$.book_title')), lower(?))>0)
              AND (?='' OR t.language=?) AND (?='' OR t.manual_version=?)
            ORDER BY CASE WHEN lower(s.heading)=lower(?) THEN 0
                          WHEN substr(lower(s.heading),1,length(?)+1)=lower(?)||':' THEN 1
                          WHEN lower(t.title)=lower(?) THEN 2
                          WHEN substr(lower(t.title),1,length(?)+1)=lower(?)||':' THEN 3
                          ELSE 4 END, bm25(search, 10, 8, 1), t.id, c.start
            LIMIT 1000
        """, (expression, library, library, library, language, language,
              manual_version, manual_version, *([_plain(query).strip()] * 6)))
        results, seen, groups = [], set(), {}
        for row in rows:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            citation = _citation(row, row["heading"], row["anchor"], row["page"])
            key = (citation["source_sha256"] or row["id"], citation["source_topic_path"])
            if key in groups:
                groups[key]["alternate_citations"].append(citation)
                continue
            if len(results) >= limit:
                continue
            results.append({"topic_id": row["id"], "title": row["title"],
                            "excerpt": row["excerpt"], "section": row["heading"],
                            "cursor": row["start"],
                            "citation": citation, "alternate_citations": []})
            groups[key] = results[-1]
    return {"results": results, "freshness": "current"}


def get_manual_topic(topic_id: str, section: str = "", cursor: int = 0,
                     max_chars: int = 12000, directory: Path | None = None) -> dict:
    """Retrieve original indexed Markdown with explicit character pagination."""
    if not re.fullmatch(r"[a-f0-9]{32}", topic_id):
        raise ValueError("Invalid topic ID; use an ID returned by search_manuals.")
    if not 1 <= max_chars <= 24000 or cursor < 0:
        raise ValueError("Use max_chars 1..24000 and a nonnegative cursor.")
    root = directory or corpus_directory()
    with _reader(root) as (db, metadata):
        _require_current(root, metadata)
        row = db.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown manual topic ID; search_manuals again.")
        sections = db.execute("SELECT * FROM sections WHERE topic_id=? ORDER BY start", (topic_id,)).fetchall()
        start, end = 0, len(row["markdown"])
        if section:
            matches = [s for s in sections if section in (s["heading"], s["anchor"])]
            if len(matches) != 1:
                raise ValueError("Section heading/anchor is missing or ambiguous; use the search result cursor.")
            start, end = matches[0]["start"], matches[0]["end"]
        offset = start + cursor if section else cursor
        if offset > end:
            raise ValueError("Cursor exceeds topic/section length.")
        stop = min(end, offset + max_chars)
        selected = next((s for s in sections if s["start"] <= offset < s["end"]), None)
        return {"topic_id": topic_id, "title": row["title"],
                "markdown": row["markdown"][offset:stop], "cursor": cursor,
                "next_cursor": (stop - start if section else stop) if stop < end else None,
                "total_chars": end - start, "freshness": "current",
                "citation": _citation(row, selected["heading"] if selected else None,
                                      selected["anchor"] if selected else None,
                                      selected["page"] if selected else None),
                "sections": [{"heading": s["heading"], "anchor": s["anchor"],
                              "page": s["page"], "cursor": s["start"]} for s in sections
                             if s["start"] < stop and s["end"] > offset]}


def main() -> int:
    """Explicit indexer entry point, also available in installed wheels."""
    import argparse

    parser = argparse.ArgumentParser(description="Index converted Control Expert manuals locally.")
    parser.add_argument("--manuals-dir", type=Path, default=corpus_directory())
    args = parser.parse_args()
    try:
        print(json.dumps(build_index(args.manuals_dir), ensure_ascii=True, indent=2))
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Indexing failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
