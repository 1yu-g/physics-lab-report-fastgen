import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import benchmark
import fastgen
import material_ingest
import review_dashboard
import workflow


class PhaseThreeWorkflowTest(unittest.TestCase):
    def test_start_creates_source_grounded_draft_and_brief(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            guide = root / "guide.txt"
            guide.write_text(
                "一、实验目的\n掌握霍尔效应测量方法。\n理解霍尔电压与电流的关系。\n"
                "二、实验原理\n霍尔元件置于磁场中会产生横向电势差。\n",
                encoding="utf-8",
            )
            result = workflow.start(
                root / "work", [guide], None, [], [],
                ["一、实验目的", "二、实验原理"], "完成前两项",
            )
            self.assertEqual(result["draft"]["filled_sections"], 2)
            report = fastgen.load(result["draft_spec"])
            self.assertEqual(report["draft_status"],
                             "source-extract-needs-rewrite-and-verification")
            self.assertIn("霍尔效应", report["sections"][0]["blocks"][0]["text"])
            with self.assertRaisesRegex(ValueError, "unreviewed draft"):
                workflow.run(root / "work", renderer="none")
            report["draft_status"] = "reviewed"
            fastgen.dump(result["draft_spec"], report)
            self.assertEqual(workflow.run(root / "work", renderer="none")["status"],
                             "render-unavailable")
            brief = fastgen.load(result["draft"]["brief"])
            self.assertEqual(brief["status"], "needs-content-review")
            self.assertEqual(brief["sections"][0]["selected_source"], str(guide.resolve()))

    def test_browser_review_updates_are_hash_guarded(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            docx = work / "report.docx"
            Document().save(docx)
            preview = work / "page-1.png"
            Image.new("RGB", (200, 300), "white").save(preview)
            fastgen.dump(work / "review.json", {
                "status": "needs-visual-review", "docx": str(docx),
                "docx_sha256": fastgen.sha256(docx),
                "pages": [{"page": 1, "preview": str(preview),
                           "preview_sha256": fastgen.sha256(preview),
                           "status": "pending", "notes": ""}],
            })
            built = review_dashboard.build(work)
            self.assertTrue(Path(built["dashboard"]).is_file())
            updated = review_dashboard.apply_updates(work, {
                "docx_sha256": fastgen.sha256(docx),
                "pages": [{"page": 1, "status": "pass", "notes": "图表和公式已检查"}],
            })
            self.assertEqual(updated["status"], "ready-to-finalize")
            self.assertEqual(updated["pages"][0]["status"], "pass")
            with self.assertRaisesRegex(ValueError, "older report"):
                review_dashboard.apply_updates(work, {
                    "docx_sha256": "old", "pages": updated["pages"],
                })

    def test_benchmark_records_cold_and_cached_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "guide.txt"
            source.write_text("实验目的\n测量电压。", encoding="utf-8")
            result = benchmark.benchmark_ingest(source, root / "bench", runs=3)
            self.assertFalse(result["samples"][0]["cache_hit"])
            self.assertTrue(all(item["cache_hit"] for item in result["samples"][1:]))
            self.assertIn("warm_median_ms", result)
            self.assertIn("speedup_median", result)
            self.assertTrue(Path(result["benchmark"]).is_file())

    def test_optional_docling_backend_has_clear_dependency_error(self):
        if importlib.util.find_spec("docling") is not None:
            self.skipTest("Docling is installed in this environment")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "scan.png"
            Image.new("RGB", (20, 20), "white").save(source)
            with self.assertRaisesRegex(RuntimeError, "Docling backend is optional"):
                material_ingest.ingest(source, root / "complex", backend="docling")


if __name__ == "__main__":
    unittest.main()
