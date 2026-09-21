import csv
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_data
import fastgen
import labfast
import material_ingest
import table_ocr
import workflow


class PhaseTwoWorkflowTest(unittest.TestCase):
    def _pptx(self, path: Path):
        slide = """<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
 <p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>二、实验原理</a:t></a:r></a:p></p:txBody></p:sp>
 <a:tbl><a:tr><a:tc><a:txBody><a:p><a:r><a:t>I/mA</a:t></a:r></a:p></a:txBody></a:tc>
 <a:tc><a:txBody><a:p><a:r><a:t>U/mV</a:t></a:r></a:p></a:txBody></a:tc></a:tr>
 <a:tr><a:tc><a:txBody><a:p><a:r><a:t>1</a:t></a:r></a:p></a:txBody></a:tc>
 <a:tc><a:txBody><a:p><a:r><a:t>2.1</a:t></a:r></a:p></a:txBody></a:tc></a:tr></a:tbl>
 </p:spTree></p:cSld></p:sld>"""
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("ppt/slides/slide1.xml", slide)
            archive.writestr("ppt/media/image1.png", b"figure-bytes")

    def _xlsx(self, path: Path):
        workbook = """<?xml version="1.0"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="霍尔数据" sheetId="1" r:id="rId1"/></sheets></workbook>"""
        rels = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
        sheet = """<?xml version="1.0"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
 <row r="1"><c r="A1" t="inlineStr"><is><t>I_mA</t></is></c><c r="B1" t="inlineStr"><is><t>U_mV</t></is></c></row>
 <row r="2"><c r="A2"><v>1</v></c><c r="B2"><v>2.1</v></c></row>
</sheetData></worksheet>"""
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("xl/workbook.xml", workbook)
            archive.writestr("xl/_rels/workbook.xml.rels", rels)
            archive.writestr("xl/worksheets/sheet1.xml", sheet)

    def test_cached_pptx_xlsx_ingestion_and_prepare(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pptx = root / "guide.pptx"
            xlsx = root / "records.xlsx"
            self._pptx(pptx)
            self._xlsx(xlsx)
            ppt_result = material_ingest.ingest(pptx, root / "ppt")
            self.assertFalse(ppt_result["cache_hit"])
            self.assertEqual(ppt_result["tables"], 1)
            self.assertEqual(ppt_result["assets"], 1)
            self.assertTrue(material_ingest.ingest(pptx, root / "ppt")["cache_hit"])
            content = Path(ppt_result["text"]).read_text(encoding="utf-8")
            self.assertIn("二、实验原理", content)
            Path(ppt_result["text"]).write_text("changed", encoding="utf-8")
            self.assertFalse(material_ingest.ingest(pptx, root / "ppt")["cache_hit"])
            xlsx_result = material_ingest.ingest(xlsx, root / "xlsx")
            self.assertEqual(xlsx_result["tables"], 1)
            table = fastgen.load(xlsx_result["manifest"])["tables"][0]
            with Path(table["path"]).open("r", encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(list(csv.reader(stream))[1], ["1", "2.1"])
            prepared = workflow.prepare(
                root / "work", [pptx], None, [], [xlsx], ["二、实验原理"], "完成原理"
            )
            inventory = fastgen.load(prepared["inventory"])
            self.assertEqual(inventory["files"][0]["extracted_tables"], 1)
            self.assertTrue(Path(inventory["files"][0]["structured_manifest"]).is_file())
            self.assertEqual(labfast.main(["--version"]), 0)

    def test_ocr_cache_corrections_and_analysis_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "record.png"
            Image.new("RGB", (200, 120), "white").save(source)
            output_dir = root / "ocr"
            output_dir.mkdir()
            preview = output_dir / "ocr-review.png"
            Image.new("RGB", (200, 120), "white").save(preview)
            csv_path = output_dir / "table-1.csv"
            csv_path.write_text("I_mA,U_mV\n1,2.0\n2,4.0\n3,6.1\n", encoding="utf-8-sig")
            cells = []
            for row_index, row in enumerate(
                    (["I_mA", "U_mV"], ["1", "2.0"], ["2", "4.0"], ["3", "6.1"]), 1):
                for column_index, value in enumerate(row, 1):
                    cells.append({"row": row_index, "column": column_index,
                                  "value": value, "bbox": [0, 0, 1, 1]})
            manifest_path = output_dir / "ocr-review.json"
            fastgen.dump(manifest_path, {
                "cache_version": table_ocr.OCR_CACHE_VERSION,
                "status": "needs-review", "source": str(source),
                "source_sha256": fastgen.sha256(source),
                "engine": "rapidocr", "language": "ch",
                "options": {"engine": "rapidocr", "language": "ch",
                            "confidence": 50, "borderless": False},
                "preview": str(preview), "preview_sha256": fastgen.sha256(preview),
                "tables": [{"id": 1, "csv": str(csv_path),
                            "csv_sha256": fastgen.sha256(csv_path),
                            "rows": 4, "columns": 2, "cells": cells,
                            "status": "pending", "review_note": ""}],
            })
            cached = table_ocr.extract(source, output_dir)
            self.assertTrue(cached["cache_hit"])
            csv_path.write_text("I_mA,U_mV\n1,2.1\n2,4.0\n3,6.1\n", encoding="utf-8-sig")
            table_ocr.verify_table(manifest_path, 1, "逐格核对并修正")
            verified = fastgen.load(manifest_path)["tables"][0]
            self.assertEqual(verified["correction_count"], 1)
            self.assertEqual(verified["corrections"][0]["verified"], "2.1")
            plan_path = root / "analysis-plan.json"
            created = analyze_data.create_plan(
                csv_path, plan_path, summaries=["U_mV"], x="I_mA", y="U_mV",
                units=["I_mA=mA", "U_mV=mV"], type_b=["U_mV=0.02"],
                ocr_review=manifest_path,
            )
            self.assertEqual(created["operations"], 2)
            plan = fastgen.load(plan_path)
            self.assertEqual(plan["operations"][0]["type_b"], 0.02)
            result = analyze_data.analyze(plan_path, root / "analysis")
            self.assertEqual(result["status"], "pass")


if __name__ == "__main__":
    unittest.main()
