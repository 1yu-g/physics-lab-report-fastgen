#!/usr/bin/env python3
"""Extract photographed tables into reviewable CSV files; never auto-approve OCR."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import fastgen

OCR_CACHE_VERSION = "2"


def _reset_managed_output(output_dir: Path, manifest_path: Path):
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        return
    if not manifest_path.is_file():
        if any(output_dir.iterdir()):
            raise ValueError("OCR output directory is not empty and has no review manifest.")
        return
    manifest = fastgen.load(manifest_path)
    managed = [manifest.get("preview")]
    managed += [item.get("csv") for item in manifest.get("tables", [])]
    managed.append(str(manifest_path))
    for value in managed:
        if not value:
            continue
        path = Path(value).resolve()
        try:
            path.relative_to(output_dir)
        except ValueError as exc:
            raise ValueError("OCR manifest points outside its output directory.") from exc
        path.unlink(missing_ok=True)


def _ocr_engine(name: str, language: str):
    try:
        if name == "rapidocr":
            from img2table.ocr import RapidOCR
            return RapidOCR(params={"Rec.lang_type": language})
        if name == "paddle":
            from img2table.ocr import PaddleOCR
            return PaddleOCR(lang=language)
        if name == "tesseract":
            from img2table.ocr import TesseractOCR
            return TesseractOCR(lang=language)
    except ImportError as exc:
        raise RuntimeError(
            f"OCR engine {name} is unavailable. Install requirements-ocr.txt or its optional backend."
        ) from exc
    raise ValueError(f"Unknown OCR engine: {name}")


def extract(source: Path, output_dir: Path, engine="rapidocr", language="ch",
            confidence=50, borderless=False, force=False):
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output_dir = output_dir.resolve()
    manifest_path = output_dir / "ocr-review.json"
    options = {
        "engine": engine, "language": language,
        "confidence": int(confidence), "borderless": bool(borderless),
    }
    if not force and manifest_path.is_file():
        cached = fastgen.load(manifest_path)
        preview = Path(cached.get("preview", ""))
        tables_exist = all(Path(item.get("csv", "")).is_file()
                           for item in cached.get("tables", []))
        if (cached.get("cache_version") == OCR_CACHE_VERSION
                and cached.get("source_sha256") == fastgen.sha256(source)
                and cached.get("options") == options
                and preview.is_file()
                and cached.get("preview_sha256") == fastgen.sha256(preview)
                and cached.get("tables") and tables_exist):
            return {
                "status": cached["status"], "manifest": str(manifest_path),
                "preview": str(preview), "table_count": len(cached["tables"]),
                "cache_hit": True,
            }
    _reset_managed_output(output_dir, manifest_path)
    try:
        from img2table.document import Image as TableImage
    except ImportError as exc:
        raise RuntimeError("img2table is unavailable. Install requirements-ocr.txt.") from exc
    ocr = _ocr_engine(engine, language)
    tables = TableImage(str(source), detect_rotation=False).extract_tables(
        ocr=ocr, implicit_rows=False, implicit_columns=False,
        borderless_tables=borderless, min_confidence=confidence
    )
    if not tables:
        raise ValueError("No table was detected. Check the image or try borderless mode.")
    preview = Image.open(source).convert("RGB")
    drawer = ImageDraw.Draw(preview)
    manifest = {
        "cache_version": OCR_CACHE_VERSION,
        "status": "needs-review",
        "source": str(source),
        "source_sha256": fastgen.sha256(source),
        "engine": engine, "language": language, "options": options,
        "tables": [],
    }
    for table_id, table in enumerate(tables, 1):
        csv_path = output_dir / f"table-{table_id}.csv"
        cells = []
        rows = []
        for row_index, row in enumerate(table.content.values(), 1):
            values = []
            for column_index, cell in enumerate(row, 1):
                value = "" if cell.value is None else str(cell.value).strip()
                values.append(value)
                bbox = cell.bbox
                box = [int(bbox.x1), int(bbox.y1), int(bbox.x2), int(bbox.y2)]
                cells.append({
                    "row": row_index, "column": column_index,
                    "value": value, "bbox": box,
                })
                drawer.rectangle(box, outline="#d1242f", width=2)
                drawer.text((box[0] + 2, box[1] + 2),
                            f"{table_id}:{row_index},{column_index}",
                            fill="#0055aa")
            rows.append(values)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
            csv.writer(stream).writerows(rows)
        manifest["tables"].append({
            "id": table_id,
            "csv": str(csv_path),
            "csv_sha256": fastgen.sha256(csv_path),
            "rows": len(rows),
            "columns": max((len(row) for row in rows), default=0),
            "cells": cells,
            "status": "pending",
            "review_note": "",
        })
    preview_path = output_dir / "ocr-review.png"
    preview.save(preview_path)
    manifest["preview"] = str(preview_path)
    manifest["preview_sha256"] = fastgen.sha256(preview_path)
    fastgen.dump(manifest_path, manifest)
    return {"status": manifest["status"], "manifest": str(manifest_path),
            "preview": str(preview_path), "table_count": len(tables),
            "cache_hit": False}


def verify_table(manifest_path: Path, table_id: int, note: str):
    if not note.strip():
        raise ValueError("State what was checked or corrected in --note.")
    manifest_path = manifest_path.resolve()
    manifest = fastgen.load(manifest_path)
    source = Path(manifest["source"])
    if fastgen.sha256(source) != manifest["source_sha256"]:
        raise ValueError("Source image changed; repeat OCR.")
    preview = Path(manifest.get("preview", ""))
    if (manifest.get("preview_sha256")
            and (not preview.is_file() or fastgen.sha256(preview) != manifest["preview_sha256"])):
        raise ValueError("OCR review preview changed; repeat OCR.")
    table = next((item for item in manifest["tables"] if item["id"] == table_id), None)
    if table is None:
        raise ValueError(f"Unknown table id: {table_id}")
    csv_path = Path(table["csv"])
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    if not rows:
        raise ValueError("The reviewed CSV is empty.")
    table["csv_sha256"] = fastgen.sha256(csv_path)
    table["rows"] = len(rows)
    table["columns"] = max(map(len, rows))
    table["status"] = "verified"
    table["review_note"] = note.strip()
    original = {
        (int(cell["row"]), int(cell["column"])): str(cell.get("value", ""))
        for cell in table.get("cells", [])
    }
    corrections = []
    row_count = max(len(rows), max((key[0] for key in original), default=0))
    column_count = max(max((len(row) for row in rows), default=0),
                       max((key[1] for key in original), default=0))
    for row_index in range(1, row_count + 1):
        for column_index in range(1, column_count + 1):
            before = original.get((row_index, column_index), "")
            after = (rows[row_index - 1][column_index - 1]
                     if row_index <= len(rows) and column_index <= len(rows[row_index - 1])
                     else "")
            if before != after:
                corrections.append({
                    "row": row_index, "column": column_index,
                    "ocr": before, "verified": after,
                })
    table["corrections"] = corrections
    table["correction_count"] = len(corrections)
    manifest["status"] = (
        "verified" if all(item["status"] == "verified" for item in manifest["tables"])
        else "needs-review"
    )
    fastgen.dump(manifest_path, manifest)
    return {"status": table["status"], "table_id": table_id, "csv": str(csv_path),
            "manifest": str(manifest_path)}


def check_verified(manifest_path: Path, csv_path: Path):
    manifest = fastgen.load(manifest_path)
    source = Path(manifest["source"])
    if not source.is_file() or fastgen.sha256(source) != manifest["source_sha256"]:
        raise ValueError("OCR source image changed or is missing.")
    csv_path = csv_path.resolve()
    item = next((row for row in manifest["tables"]
                 if Path(row["csv"]).resolve() == csv_path), None)
    if item is None or item["status"] != "verified":
        raise ValueError("OCR table must be visually checked and verified before analysis.")
    if fastgen.sha256(csv_path) != item["csv_sha256"]:
        raise ValueError("Verified OCR CSV changed; check it again.")
    return item


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("extract")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--engine", choices=("rapidocr", "paddle", "tesseract"),
                   default="rapidocr")
    p.add_argument("--language", default="ch")
    p.add_argument("--confidence", type=int, default=50)
    p.add_argument("--borderless", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="Discard the matching cached OCR result and run recognition again")
    p = sub.add_parser("verify")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--table-id", type=int, required=True)
    p.add_argument("--note", required=True)
    return parser.parse_args()


def main():
    args = cli()
    try:
        if args.command == "extract":
            result = extract(args.input, args.output_dir, args.engine,
                             args.language, args.confidence, args.borderless, args.force)
        else:
            result = verify_table(args.manifest, args.table_id, args.note)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"table_ocr: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
