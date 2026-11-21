"""Focused regression checks for manual discovery, navigation, and resumable exports."""

from pathlib import Path
import tempfile
import unittest

from export_ce_help import convert_html, convert_one, destination, discover, rewrite_link


class ExportHelpTests(unittest.TestCase):
    def test_language_selection_includes_shared_documents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ["PunitHelp/1033/base.chm", "PunitHelp/1040/base.chm",
                         "PLC_Simulator/Eng/sim.chm", "ReleaseNotes.pdf", "code.dll"]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            found = {path.as_posix() for path in discover(root, {"en"})}
            self.assertEqual(found, {"PunitHelp/1033/base.chm", "PLC_Simulator/Eng/sim.chm", "ReleaseNotes.pdf"})

    def test_cross_book_link_preserves_anchor(self):
        manual = Path("PunitHelp/1033/baselib.chm")
        archives = {"punithelp/1033/sandsw.chm": "chm/PunitHelp/1033/sandsw"}
        actual = rewrite_link("ms-its:sandsw.chm::/topic.htm#Some.ID", Path("sub/start.htm"), manual, archives)
        self.assertEqual(actual, "../../sandsw/topic.md#Some.ID")

    def test_missing_external_book_remains_identifiable(self):
        link = "ms-its:missing.chm::/topic.htm"
        self.assertEqual(rewrite_link(link, Path("a.htm"), Path("book.chm"), {}), link)

    def test_relative_link_escapes_spaces(self):
        self.assertEqual(rewrite_link("../Other%20Page.HTM#top", Path("sub/a.htm"), Path("book.chm"), {}),
                         "../Other%20Page.md#top")

    def test_named_anchors_and_redirects_survive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "topic.htm"
            source.write_text('<html><head><title>Redirect</title><meta http-equiv="Refresh" '
                              'content="0; URL=next.htm"></head><body><a name="CE.123"></a></body></html>')
            target = root / "topic.md"
            convert_html(source, target, Path("topic.htm"), Path("book.chm"), {})
            text = target.read_text(encoding="utf-8")
            self.assertIn('<a id="CE.123"></a>', text)
            self.assertIn("[Continue to the topic](next.md)", text)
            self.assertNotIn("<script", text)

    def test_chm_layout_title_becomes_heading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "topic.htm"
            source.write_text('<html><body><table class="titlebar"><tr><td><div class="titlemap">'
                              '<a name="KW1"></a>Topic title</div></td></tr></table>'
                              '<div class="titleblock">Parameters</div><p>Details</p></body></html>')
            target = root / "topic.md"
            convert_html(source, target, Path("topic.htm"), Path("book.chm"), {})
            text = target.read_text(encoding="utf-8")
            self.assertIn("Topic title", text)
            self.assertIn("## Parameters", text)
            self.assertIn('<a id="KW1"></a>', text)
            self.assertNotIn("| ---", text)

    def test_standalone_html_navigation_uses_export_folders(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "topic.htm"
            source.write_text('<html><body><h1>Topic</h1><a href="next.HTM#ref">Next</a></body></html>')
            target = root / "_index.md"
            convert_html(source, target, Path("topic.htm"), Path("Lib/Eng/topic.HTM"), {}, standalone=True)
            self.assertIn("../next/_index.md#ref", target.read_text(encoding="utf-8"))

    def test_cache_recovers_missing_files_and_changed_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "topic.htm"
            source.write_text("<h1>First</h1>")
            job = {"source": str(source), "relative": "topic.htm", "output": str(root / "output"),
                   "converter": "test", "force": False}
            self.assertEqual(convert_one(job)["status"], "converted")
            self.assertEqual(convert_one(job)["status"], "cached")
            (root / "output" / destination(Path("topic.htm")) / "_index.md").unlink()
            self.assertEqual(convert_one(job)["status"], "converted")
            source.write_text("<h1>Second</h1>")
            self.assertEqual(convert_one(job)["title"], "Second")

    def test_standalone_pdf_link_points_to_converted_manual(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "topic.htm"
            source.write_text('<h1>Topic</h1><a href="../HELP/Manual.pdf">Read manual</a>')
            target = root / "_index.md"
            convert_html(source, target, Path("topic.htm"), Path("Lib/ENG/topic.HTM"), {}, standalone=True)
            self.assertIn("../../../../pdf/Lib/HELP/Manual/_index.md", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
