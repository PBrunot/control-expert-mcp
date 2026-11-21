"""Export installed Control Expert CHM, HTML, and PDF manuals to local Markdown.

No CE automation or PLC connection is used. See --help and README.md.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import html
from importlib.metadata import version
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote, unquote, urlsplit

from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_INSTALL = Path(r"C:\Program Files (x86)\Schneider Electric\EcoStruxure Control Expert 16.4")
HTML_SUFFIXES = {".htm", ".html", ".xhtml"}
LANGUAGES = {
    "en": {"1033", "eng", "en-us"},
    "it": {"1040", "ita", "it-it"},
    "de": {"1031", "ger", "de-de"},
    "fr": {"1036", "fre", "fr-fr"},
    "es": {"1034", "spa", "es-es"},
    "zh": {"2052", "chi", "zh-cn"},
}
ASSETS = {".png", ".gif", ".jpg", ".jpeg", ".svg", ".bmp", ".webp", ".wmf", ".emf", ".ico"}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def language_of(path: Path) -> str | None:
    parts = {part.lower() for part in path.parts}
    return next((key for key, names in LANGUAGES.items() if parts & names), None)


def destination(relative: Path) -> Path:
    if relative.suffix.lower() == ".chm":
        return Path("chm") / relative.with_suffix("")
    if relative.suffix.lower() == ".pdf":
        return Path("pdf") / relative.with_suffix("")
    return Path("html") / relative.with_suffix("")


def discover(install: Path, languages: set[str]) -> list[Path]:
    result = []
    for path in install.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in HTML_SUFFIXES | {".chm", ".pdf"}:
            continue
        relative = path.relative_to(install)
        language = language_of(relative)
        if language is None or language in languages:
            result.append(relative)
    return sorted(result, key=lambda p: p.as_posix().lower())


def local_url(path: str, fragment: str = "") -> str:
    result = quote(path.replace("\\", "/"), safe="/.-_")
    return result + ("#" + quote(fragment, safe=".-_:") if fragment else "")


def rewrite_link(value: str, topic: Path, manual: Path, archives: dict[str, str]) -> str:
    """Resolve ordinary links and CHM cross-book links without losing fragments."""
    value = value.strip().replace("\\", "/")
    if "::" in value:
        archive, target = value.split("::", 1)
        archive = re.sub(r"^(?:mk:@MSITStore:|ms-its:|its:)", "", archive, flags=re.I)
        name = archive.rsplit("/", 1)[-1].lower()
        other = archives.get((manual.parent / name).as_posix().lower())
        if other is None:
            return value  # Leave unavailable external manuals identifiable.
        parsed = urlsplit(target.lstrip("/"))
        path = Path(unquote(parsed.path))
        if path.suffix.lower() in HTML_SUFFIXES:
            path = path.with_suffix(".md")
        elif not parsed.path:
            path = Path("_index.md")
        target_path = Path(other) / path
        origin = destination(manual) / topic.with_suffix(".md").parent
        return local_url(os.path.relpath(target_path, origin), unquote(parsed.fragment))
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return value
    path = unquote(parsed.path)
    if Path(path).suffix.lower() in HTML_SUFFIXES:
        path = str(Path(path).with_suffix(".md"))
    if path.startswith("/"):
        path = posixpath.relpath(path.lstrip("/"), topic.parent.as_posix())
    return local_url(path, unquote(parsed.fragment))


def convert_html(source: Path, target: Path, topic: Path, manual: Path,
                 archives: dict[str, str], standalone: bool = False) -> str:
    soup = BeautifulSoup(source.read_bytes(), "lxml")
    heading = soup.find(["h1", "h2"]) or soup.select_one(".titlemap") or soup.title
    title = heading.get_text(" ", strip=True) if heading else source.stem
    redirect = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
    redirect_target = None
    if redirect:
        match = re.search(r"url\s*=\s*['\"]?([^'\"]+)", redirect.get("content", ""), re.I)
        if match:
            redirect_target = match[1]
    # CE uses layout tables for its title/navigation bar; keep the title and
    # anchor IDs, without turning those tables into malformed Markdown tables.
    for bar in soup.select("table.titlebar"):
        replacement = soup.new_tag("h1")
        replacement.string = title
        for anchor in list(bar.find_all("a")):
            if anchor.get("name") or anchor.get("id"):
                replacement.insert(0, anchor.extract())
        bar.replace_with(replacement)
    for block in soup.select(".titleblock"):
        block.name = "h2"
    for bar in soup.select("table.headerfoot"):
        bar.name = "div"
        for tag in list(bar.find_all(["tr", "td", "tbody"])):
            tag.unwrap()
    # Preserve IDs/named anchors explicitly: Markdown heading slugs differ from CE IDs.
    anchors: dict[str, str] = {}
    for element in list(soup.find_all(True)):
        if element.parent is None:
            continue
        identifier = element.get("id") or (element.get("name") if element.name == "a" else None)
        if identifier:
            token = f"CEANCHORPLACEHOLDER{len(anchors)}END"
            anchors[token] = f'<a id="{html.escape(str(identifier), quote=True)}"></a>'
            element.insert_before(NavigableString(token))
    for element in soup.find_all(["script", "style", "head", "object", "noscript"]):
        element.decompose()
    for element in soup.find_all("v:imagedata"):
        image = soup.new_tag("img", src=element.get("src", ""))
        element.replace_with(image)
    def link_url(value: str, image: bool = False) -> str:
        parsed = urlsplit(value.replace("\\", "/"))
        if standalone and not image and not parsed.scheme and not parsed.netloc and parsed.path:
            path = Path(posixpath.normpath((manual.parent / unquote(parsed.path)).as_posix()))
            if path.suffix.lower() in HTML_SUFFIXES | {".pdf"}:
                relative = os.path.relpath(destination(path) / "_index.md", destination(manual))
                return local_url(relative, unquote(parsed.fragment))
        return rewrite_link(value, topic, manual, archives)

    for element in soup.find_all(["a", "img", "frame", "iframe"]):
        attribute = "href" if element.name == "a" else "src"
        value = element.get(attribute)
        if not value:
            continue
        if value.lower().startswith("javascript:"):
            del element[attribute]
        else:
            element[attribute] = link_url(value, image=element.name == "img")
        if element.name in {"frame", "iframe"}:
            link = soup.new_tag("a", href=element.get(attribute, ""))
            link.string = element.get("title") or value
            element.replace_with(link)
    body = markdownify(str(soup.body or soup), heading_style="ATX", bullets="-", strip=["font"])
    for token, anchor in anchors.items():
        body = body.replace(token, anchor)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if redirect_target:
        body = f"[Continue to the topic]({link_url(redirect_target)})\n\n{body}"
    visible = re.sub(r'<a id="[^"]*"></a>', "", body).lstrip()
    if not re.match(r"^#\s", visible):
        body = f"# {title}\n\n{body}"
    provenance = (f"<!-- Source: {manual.as_posix()} :: {topic.as_posix()}; "
                  "generated from locally installed Schneider Electric documentation. -->\n\n")
    write_text(target, provenance + body + "\n")
    return title


def convert_chm(source: Path, folder: Path, manual: Path, archives: dict[str, str],
                seven_zip: str, timeout: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="ce-help-") as temporary:
        extracted = Path(temporary)
        process = subprocess.run(
            [seven_zip, "x", "-y", "-bso0", "-bsp0", f"-o{extracted}", str(source)],
            capture_output=True, text=True, errors="replace", timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process.returncode:
            raise RuntimeError(f"7-Zip exit {process.returncode}: {process.stderr[-1500:]}")
        topics = sorted(p for p in extracted.rglob("*") if p.suffix.lower() in HTML_SUFFIXES)
        if not topics:
            raise RuntimeError("CHM extraction produced no HTML topics")
        titles = {}
        outputs = []
        for path in topics:
            relative = path.relative_to(extracted)
            target = folder / relative.with_suffix(".md")
            titles[relative.as_posix().lower()] = convert_html(path, target, relative, manual, archives)
            outputs.append(target.relative_to(folder).as_posix())
        for asset in extracted.rglob("*"):
            if asset.is_file() and asset.suffix.lower() in ASSETS:
                relative = asset.relative_to(extracted)
                target = folder / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(asset, target)
                outputs.append(relative.as_posix())
        toc = []
        book_title = None
        for contents in sorted(extracted.rglob("*.hhc")):
            soup = BeautifulSoup(contents.read_bytes(), "lxml")
            for obj in soup.find_all("object", attrs={"type": re.compile("text/sitemap", re.I)}):
                params = {p.get("name", "").lower(): p.get("value", "") for p in obj.find_all("param")}
                label = params.get("name", "")
                target = params.get("local", "")
                if label and book_title is None:
                    book_title = label
                if label and target:
                    depth = max(0, len(obj.find_parents("ul")) - 1)
                    url = rewrite_link(target, Path("_index.htm"), manual, archives)
                    toc.append("  " * depth + f"- [{label.replace('[', '').replace(']', '')}]({url})")
        title = book_title or source.stem
        index = [f"# {title}", "", f"Source: `{manual.as_posix()}`", "", "## Contents", ""]
        index.extend(toc or ["No compiled table of contents; use the topic list below."])
        index.extend(["", "## All topics", ""])
        for path in topics:
            relative = path.relative_to(extracted)
            label = titles[relative.as_posix().lower()].replace("[", "").replace("]", "")
            index.append(f"- [{label}]({local_url(relative.with_suffix('.md').as_posix())})")
        write_text(folder / "_index.md", "\n".join(index) + "\n")
        outputs.append("_index.md")
        return {"title": title, "topics": len(topics), "outputs": outputs,
                "index": "_index.md", "warnings": []}


def convert_pdf(source: Path, folder: Path, manual: Path) -> dict:
    import pymupdf

    # Keep native-text conversion deterministic and independent of ONNX/OCR.
    # PyMuPDF 2.1's optional ONNX engine crashes during import on the tested host.
    pymupdf.use_layout(False)
    folder.mkdir(parents=True, exist_ok=True)
    images = folder / "images"
    images.mkdir(exist_ok=True)
    with pymupdf.open(source) as document:
        title = document.metadata.get("title") or source.stem
        pages = len(document)
        blank = [page.number + 1 for page in document if not page.get_text().strip()]
        # Native text extraction only: do not launch OCR or download OCR models.
        chunks = document.to_markdown(
            page_chunks=True, write_images=True, image_path=str(images),
            image_format="png", show_progress=False, force_text=True,
        )
        parts = [f"# {title}\n\nSource: `{manual.as_posix()}`\n"]
        for number, chunk in enumerate(chunks, start=1):
            text = chunk["text"].replace(str(images).replace("\\", "/") + "/", "images/")
            text = text.replace(str(images) + os.sep, "images/")
            parts.append(f'\n<a id="page-{number}"></a>\n\n## Page {number}\n\n{text.strip()}\n')
        write_text(folder / "_index.md", "\n".join(parts))
    return {"title": title, "topics": pages,
            "outputs": [p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()],
            "index": "_index.md", "pdf_engine": "pymupdf-native-text",
            "warnings": [f"Pages without native text (no OCR): {blank}"] if blank else []}


def convert_one(job: dict) -> dict:
    source = Path(job["source"])
    manual = Path(job["relative"])
    output = Path(job["output"])
    folder = output / destination(manual)
    state_path = folder / ".conversion.json"
    fingerprint = {"source_sha256": digest(source), "converter": job["converter"]}
    if not job["force"] and state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        if previous.get("fingerprint") == fingerprint and all((folder / p).is_file() for p in previous["outputs"]):
            return {**previous, "status": "cached"}
    folder.mkdir(parents=True, exist_ok=True)
    # Invalidate completion before writing, so interrupted/failed work is never cached.
    state_path.unlink(missing_ok=True)
    if source.suffix.lower() == ".chm":
        result = convert_chm(source, folder, manual, job["archives"], job["seven_zip"], job["timeout"])
    elif source.suffix.lower() == ".pdf":
        result = convert_pdf(source, folder, manual)
    else:
        title = convert_html(source, folder / "_index.md", Path(source.name), manual, {}, standalone=True)
        outputs = ["_index.md"]
        # Standalone HTML exports carry adjacent image assets; CHM assets are handled above.
        soup = BeautifulSoup(source.read_bytes(), "lxml")
        warnings = []
        for image in soup.find_all("img", src=True):
            parsed = urlsplit(image["src"].replace("\\", "/"))
            if parsed.scheme or parsed.netloc:
                continue
            relative = Path(unquote(parsed.path))
            if relative.is_absolute() or ".." in relative.parts:
                warnings.append(f"Image outside topic directory: {image['src']}")
                continue
            asset = source.parent / relative
            if asset.is_file() and asset.suffix.lower() in ASSETS:
                target = folder / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(asset, target)
                outputs.append(relative.as_posix())
        result = {"title": title, "topics": 1, "outputs": outputs, "index": "_index.md", "warnings": warnings}
    result.update(source=manual.as_posix(), fingerprint=fingerprint,
                  folder=folder.relative_to(output).as_posix(), status="converted")
    write_text(state_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path, default=DEFAULT_INSTALL)
    parser.add_argument("--output", type=Path, default=REPOSITORY / "manuals" / "ce-16.4")
    parser.add_argument("--languages", nargs="+", choices=[*LANGUAGES, "all"], default=["en"])
    parser.add_argument("--include", action="append", default=[], help="Source path substring filter; repeatable")
    parser.add_argument("--list", action="store_true", help="Inventory only; do not create output")
    parser.add_argument("--jobs", type=int, default=4, help="Worker processes (default: 4)")
    parser.add_argument("--seven-zip", help="Path to 7z.exe (automatically discovered by default)")
    parser.add_argument("--timeout", type=int, default=180, help="Per-CHM extraction timeout in seconds")
    parser.add_argument("--force", action="store_true", help="Regenerate unchanged sources")
    args = parser.parse_args()
    if args.jobs < 1 or args.timeout < 1:
        parser.error("--jobs and --timeout must be positive")
    install = args.install_dir.resolve()
    output = args.output.resolve()
    if not install.is_dir():
        parser.error(f"Installation directory not found: {install}")
    if output == install or install in output.parents or output in install.parents:
        parser.error("Output must be separate from the installation directory")
    languages = set(LANGUAGES) if "all" in args.languages else set(args.languages)
    inventory = discover(install, languages)
    selected = [p for p in inventory if not args.include or any(s.lower() in p.as_posix().lower() for s in args.include)]
    counts = {suffix: sum(p.suffix.lower() == suffix for p in selected) for suffix in [".chm", ".pdf", ".htm", ".html"]}
    print(json.dumps({"install": str(install), "output": str(output), "languages": sorted(languages),
                      "sources": len(selected), "by_extension": counts}), flush=True)
    if args.list:
        for path in selected:
            print(path.as_posix())
        return 0
    if not selected:
        parser.error("No matching manuals found")
    seven_zip = args.seven_zip or shutil.which("7z")
    if not seven_zip:
        seven_zip = next((str(p) for p in [Path(r"C:\Program Files\7-Zip\7z.exe"),
                         Path(r"C:\Program Files (x86)\7-Zip\7z.exe")] if p.is_file()), None)
    if any(p.suffix.lower() == ".chm" for p in selected) and not seven_zip:
        parser.error("Install 7-Zip or supply --seven-zip C:\\path\\7z.exe")
    marker = output / ".ce-help-output"
    if output.exists() and any(output.iterdir()) and not marker.exists():
        parser.error("Refusing an existing nonempty output folder without .ce-help-output")
    output.mkdir(parents=True, exist_ok=True)
    write_text(marker, "Generated local Schneider help; do not commit or redistribute.\n")
    archives = {p.as_posix().lower(): destination(p).as_posix() for p in inventory if p.suffix.lower() == ".chm"}
    dependencies = {name: version(name) for name in ["beautifulsoup4", "lxml", "markdownify", "pymupdf"]}
    converter = digest(Path(__file__)) + json.dumps(dependencies, sort_keys=True)
    jobs = [dict(source=str(install / p), relative=p.as_posix(), output=str(output),
                 archives=archives, seven_zip=seven_zip, timeout=args.timeout,
                 force=args.force, converter=converter) for p in selected]
    results = []
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(convert_one, job): job for job in jobs}
        for number, future in enumerate(as_completed(futures), start=1):
            job = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"source": job["relative"], "status": "failed", "error": str(exc)}
            results.append(result)
            print(f"[{number}/{len(jobs)}] {result['status']}: {result['source']}"
                  + (f" -- {result['error']}" if result['status'] == 'failed' else ''), flush=True)
    results.sort(key=lambda result: result["source"].lower())
    # Merge partial runs, retaining successful manuals from earlier language/filter runs.
    manifest_path = output / "manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    combined = {r["source"]: r for r in previous.get("manuals", [])}
    combined.update({r["source"]: r for r in results})
    manifest = {"installation": str(install), "generated_at": datetime.now(timezone.utc).isoformat(),
                "dependencies": dependencies, "manuals": sorted(combined.values(), key=lambda r: r["source"].lower())}
    write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    index = ["# Control Expert installed manuals", "", f"Source installation: `{install}`", "",
             "Generated for local reference. Copyright and notices remain with Schneider Electric.", "",
             "CHM topics retain images and anchors. PDF layout, complex tables, and diagrams may need comparison with the original; OCR is disabled.", "",
             "See `manifest.json` for source hashes, extraction warnings, and failures.", ""]
    for result in manifest["manuals"]:
        if result["status"] == "failed":
            index.append(f"- **FAILED** `{result['source']}`: {result['error']}")
        else:
            link = local_url(f"{result['folder']}/{result['index']}")
            label = result["title"].replace("[", "").replace("]", "")
            index.append(f"- [{label}]({link}) — `{result['source']}` ({result['topics']} topics/pages)")
    write_text(output / "README.md", "\n".join(index) + "\n")
    failed = sum(result["status"] == "failed" for result in results)
    print(f"Finished: {len(results) - failed} succeeded, {failed} failed. Index: {output / 'README.md'}")
    return 1 if failed else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
