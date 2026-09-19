import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_data
import fastgen
import figure_tools
import table_ocr
import workflow


class AdvancedWorkflowTest(unittest.TestCase):
    def test_verified_csv_analysis_plot_and_invalidation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo = root / "record.png"
            Image.new("RGB", (300, 200), "white").save(photo)
            csv_path = root / "table-1.csv"
            csv_path.write_text("I_mA,U_mV\n1,2.1\n2,4.0\n3,6.2\n4,7.9\n", encoding="utf-8")
            review = root / "ocr-review.json"
            fastgen.dump(review, {
                "status": "needs-review", "source": str(photo),
                "source_sha256": fastgen.sha256(photo),
                "tables": [{"id": 1, "csv": str(csv_path),
                            "csv_sha256": fastgen.sha256(csv_path),
                            "status": "pending", "review_note": ""}],
            })
            with self.assertRaisesRegex(ValueError, "visually checked"):
                table_ocr.check_verified(review, csv_path)
            table_ocr.verify_table(review, 1, "Compared every cell with the source image")
            table_ocr.check_verified(review, csv_path)
            plan = root / "analysis-plan.json"
            fastgen.dump(plan, {
                "input": "table-1.csv", "ocr_review": "ocr-review.json",
                "units": {"I_mA": "mA", "U_mV": "mV"},
                "operations": [
                    {"id": "voltage", "type": "summary", "column": "U_mV", "type_b": 0.02},
                    {"id": "fit", "type": "linear_fit", "x": "I_mA", "y": "U_mV"},
                    {"id": "resistance", "type": "formula", "expression": "U / I",
                     "variables": {"U": {"value": 0.1, "uncertainty": 0.001, "unit": "V"},
                                   "I": {"value": 0.01, "uncertainty": 0.0001, "unit": "A"}},
                     "output_unit": "ohm"},
                ],
            })
            result = analyze_data.analyze(plan, root / "analysis")
            analysis_path = Path(result["analysis"])
            analysis = analyze_data.check_analysis(analysis_path)
            self.assertAlmostEqual(analysis["results"]["voltage"]["mean"]["value"], 5.05)
            self.assertAlmostEqual(analysis["results"]["fit"]["slope"]["value"], 1.96)
            self.assertAlmostEqual(analysis["results"]["resistance"]["result"]["value"], 10.0)
            self.assertAlmostEqual(analysis["results"]["resistance"]["result"]["uncertainty"], 0.141421356, places=7)
            self.assertEqual(analysis["results"]["resistance"]["result"]["unit"], "ohm")
            figure = root / "fit.png"
            figure_tools.plot_fit(analysis_path, "fit", figure)
            self.assertTrue(figure.is_file())
            self.assertGreater(figure.stat().st_size, 10000)
            spec = {"sections": [{"blocks": [{"text": "斜率 {{result.fit.slope.value:.3f}} {{result.fit.slope.unit}}"}]}]}
            resolved = workflow.resolve_results(spec, analysis)
            self.assertIn("1.960", resolved["sections"][0]["blocks"][0]["text"])
            work = root / "work"
            work.mkdir()
            report_spec = work / "report.json"
            fastgen.dump(report_spec, {
                "title": "合成数据测试报告",
                "analysis_manifest": str(analysis_path),
                "sections": [{"title": "一、结果", "blocks": [
                    {"type": "paragraph", "text": "拟合斜率 {{result.fit.slope.value:.3f}} {{result.fit.slope.unit}}。"},
                    {"type": "figure", "path": str(figure), "caption": "拟合与残差图"}
                ]}]
            })
            built = workflow.run(work, renderer="none")
            self.assertEqual(built["status"], "render-unavailable")
            from docx import Document
            body = "\n".join(p.text for p in Document(built["docx"]).paragraphs)
            self.assertIn("1.960", body)
            self.assertEqual(fastgen.load(built["qa"])["analysis_manifest"], str(analysis_path))
            csv_path.write_text("I_mA,U_mV\n1,999\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source changed"):
                analyze_data.check_analysis(analysis_path)

    def test_safe_formula_and_schematic_and_image_copy(self):
        with self.assertRaises(ValueError):
            analyze_data.safe_expression("__import__('os').system('echo bad')", {})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / "source.png"
            Image.new("RGB", (100, 80), "white").save(original)
            digest = fastgen.sha256(original)
            processed = root / "processed.png"
            figure_tools.preprocess(original, processed, crop=[10, 10, 90, 70], grayscale=True)
            self.assertEqual(fastgen.sha256(original), digest)
            with Image.open(processed) as image:
                self.assertEqual(image.size, (80, 60))
            spec = root / "schematic.json"
            fastgen.dump(spec, {"components": [
                {"type": "source_v", "direction": "up", "label": "V"},
                {"type": "resistor", "direction": "right", "label": "R"},
                {"type": "ground", "direction": "down"},
            ]})
            output = root / "circuit.png"
            figure_tools.schematic(spec, output)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
