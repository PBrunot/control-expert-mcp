"""Offline manual service checks using synthetic, redistributable text only."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest

from control_expert_mcp.documentation import (
    INDEX_NAME, _reader, build_index, documentation_status, get_manual_topic, search_manuals,
)


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        folder = self.root / "chm/en/book"
        folder.mkdir(parents=True)
        self.markdown = ('<a id="TON"></a>\n# TON\n\nTimer example.\n\n'
                         '<a id="parameters"></a>\n## Parameters\n\n'
                         '| Name | Type |\n| --- | --- |\n| IN | BOOL |\n\n'
                         '```st\n# not a heading\ntimer(IN := start);\n```\n')
        (folder / "ton.md").write_text(self.markdown, encoding="utf-8")
        (folder / "read.md").write_text('# READ\\_VAR\n\nExchange example.\n', encoding="utf-8")
        (folder / "noise.md").write_text('# Broad topic\n\nTON ' * 20, encoding="utf-8")
        (self.root / "unlisted.md").write_text('unlistedsecret', encoding="utf-8")
        pdf = self.root / "pdf/book"
        pdf.mkdir(parents=True)
        (pdf / "_index.md").write_text('# PDF Book\n\n<a id="page-1"></a>\n## Page 1\n\n'
                                      'Page one.\n\n<a id="page-2"></a>\n## Page 2\n\n'
                                      'UniquePDFtext\n\n### Constraints\n\nRestrictions.\n', encoding="utf-8")
        self.manifest = {
            "installation": r"C:\Vendor\Control Expert 16.4",
            "manuals": [
                {"status": "cached", "source": "Help/1033/base.chm", "title": "Base Library",
                 "folder": "chm/en/book", "outputs": ["ton.md", "read.md", "noise.md"],
                 "manual_version": "14.0", "document_revision": "R2", "library": "Base",
                 "fingerprint": {"source_sha256": "abc", "converter": "v1"},
                 "warnings": ["Check diagrams"]},
                {"status": "converted", "source": "shared.pdf", "title": "PDF Book",
                 "folder": "pdf/book", "outputs": ["_index.md"], "warnings": ["No OCR"]},
                {"status": "failed", "source": "failed.chm", "folder": ".",
                 "outputs": ["unlisted.md"], "error": "conversion failed"},
            ],
        }
        self.write_manifest()
        build_index(self.root)

    def write_manifest(self):
        (self.root / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def search(self, query, **kwargs):
        return search_manuals(query, directory=self.root, **kwargs)["results"]

    def test_exact_symbol_ranking_citations_and_version_separation(self):
        result = self.search("TON")[0]
        self.assertEqual(result["title"], "TON")
        citation = result["citation"]
        self.assertEqual(citation["installation_version"], "16.4")
        self.assertEqual(citation["manual_version"], "14.0")
        self.assertEqual(citation["document_revision"], "R2")
        self.assertEqual(citation["source_sha256"], "abc")
        self.assertEqual(citation["anchor"], "TON")
        self.assertEqual(citation["language"], "en")
        self.assertEqual(citation["warnings"], ["Check diagrams"])
        self.assertEqual(self.search("TON", manual_version="16.4"), [])
        self.assertTrue(self.search("TON", manual_version="14.0", language="en", library="Base"))
        self.assertEqual(self.search("TON", installation_version="14.0"), [])
        self.assertEqual(self.search("TON", language="it"), [])

    def test_successful_allowlist_and_literal_fts_queries(self):
        self.assertEqual(self.search("unlistedsecret"), [])
        self.assertEqual(self.search("READ_VAR")[0]["title"], "READ_VAR")
        self.assertTrue(self.search('"READ_VAR" OR * ('))
        with self.assertRaises(ValueError):
            self.search("*()")
        status = documentation_status(self.root)
        self.assertTrue(status["ready"])
        self.assertEqual(status["counts"]["topics"], 4)
        self.assertEqual(len(status["conversion_failures"]), 1)

    def test_original_markdown_pagination_and_section_boundaries(self):
        topic_id = self.search("TON")[0]["topic_id"]
        chunks, cursor = [], 0
        while cursor is not None:
            response = get_manual_topic(topic_id, cursor=cursor, max_chars=19, directory=self.root)
            chunks.append(response["markdown"])
            cursor = response["next_cursor"]
        self.assertEqual("".join(chunks), self.markdown)
        response = get_manual_topic(topic_id, section="parameters", directory=self.root)
        self.assertIn('| IN | BOOL |', response["markdown"])
        self.assertIn('# not a heading', response["markdown"])
        self.assertEqual(response["citation"]["anchor"], "parameters")
        self.assertEqual(len(response["sections"]), 1)
        with self.assertRaises(ValueError):
            get_manual_topic(topic_id, cursor=10000, directory=self.root)

    def test_pdf_pages_and_unknown_metadata(self):
        result = self.search("UniquePDFtext")[0]
        self.assertEqual(result["citation"]["page"], 2)
        self.assertEqual(result["citation"]["anchor"], "page-2")
        self.assertIsNone(result["citation"]["manual_version"])
        result = self.search("Restrictions")[0]
        self.assertEqual(result["citation"]["page"], 2)

    def test_parallel_readers_and_large_search_passages(self):
        markdown = '# LongReference\n\n' + ('Some introductory text.\n\n' * 400)
        markdown += ('```st\n' + 'value := value + 1;\n' * 400 + '```\n\nTailSymbol\n')
        (self.root / "chm/en/book/long.md").write_text(markdown, encoding="utf-8")
        self.manifest["manuals"][0]["outputs"].append("long.md")
        self.write_manifest()
        build_index(self.root)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(self.search, ["TON", "READ_VAR", "TailSymbol", "TON"]))
        self.assertTrue(all(results))
        with _reader(self.root) as (db, _):
            chunks = db.execute("SELECT t.markdown, c.start, c.end FROM chunks c "
                                "JOIN sections s ON s.rowid=c.section_id JOIN topics t ON t.id=s.topic_id "
                                "WHERE t.title='LongReference'").fetchall()
            self.assertGreater(len(chunks), 1)
            self.assertEqual(sum(chunk["markdown"][chunk["start"]:chunk["end"]].count('```')
                                 for chunk in chunks), 2)
            self.assertTrue(all(chunk["markdown"][chunk["start"]:chunk["end"]].count('```') in (0, 2)
                                for chunk in chunks))

    def test_duplicate_sources_preserve_alternate_citations(self):
        duplicate = {**self.manifest["manuals"][0], "source": "OtherHelp/1033/base.chm"}
        self.manifest["manuals"].append(duplicate)
        self.write_manifest()
        build_index(self.root)
        result = self.search("TON")[0]
        self.assertEqual(len(result["alternate_citations"]), 1)
        self.assertNotEqual(result["citation"]["topic_id"], result["alternate_citations"][0]["topic_id"])

    def test_missing_stale_and_read_only(self):
        with _reader(self.root) as (db, _):
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("DELETE FROM topics")
        self.manifest["generated_at"] = "changed"
        self.write_manifest()
        self.assertEqual(documentation_status(self.root)["freshness"], "stale")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.search("TON")
        (self.root / INDEX_NAME).unlink()
        self.assertIn("index missing", documentation_status(self.root)["error"])
        self.assertFalse((self.root / INDEX_NAME).exists())
        (self.root / "manifest.json").unlink()
        self.assertIn("manifest missing", documentation_status(self.root)["error"])

    def test_failed_rebuild_keeps_previous_index_and_stable_ids(self):
        original = self.search("TON")[0]["topic_id"]
        build_index(self.root)
        self.assertEqual(self.search("TON")[0]["topic_id"], original)
        old_bytes = (self.root / INDEX_NAME).read_bytes()
        self.manifest["manuals"][0]["outputs"].append("../escape.md")
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            build_index(self.root)
        self.assertEqual((self.root / INDEX_NAME).read_bytes(), old_bytes)
        self.assertEqual(list(self.root.glob(".ce-help-*.sqlite3")), [])
        with self.assertRaises(ValueError):
            get_manual_topic("../secret", directory=self.root)

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "secret.md"
            external.write_text("private", encoding="utf-8")
            link = self.root / "chm/en/book/link.md"
            try:
                link.symlink_to(external)
            except OSError:
                self.skipTest("Symlink privileges unavailable")
            self.manifest["manuals"][0]["outputs"].append("link.md")
            self.write_manifest()
            with self.assertRaisesRegex(ValueError, "escapes"):
                build_index(self.root)


if __name__ == "__main__":
    unittest.main()
