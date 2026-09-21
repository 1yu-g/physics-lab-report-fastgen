#!/usr/bin/env python3
"""Create a source-grounded report draft and evidence brief from an inventory."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fastgen

VERSION = "1"
HEADING = re.compile(r"^(?:第?[一二三四五六七八九十]+[、.．章节]|\d+[、.．])\s*\S+")
TOP_KEY = re.compile(r"^第?([一二三四五六七八九十]+|\d+)[、.．章节]")
STRUCTURE_HEADING = re.compile(r"^##\s+(?:Page|Slide|Sheet|Paragraph|Document|Table)\b", re.I)
FORMULA_LINE = re.compile(r"^[A-Za-zΑ-Ωα-ω][^。；;]{0,100}=[^。；;]{1,120}$")


def _clean_lines(text: str):
    return [line.strip() for line in text.splitlines()
            if line.strip() and not STRUCTURE_HEADING.match(line.strip())]


def _normalize(value: str):
    return re.sub(r"[\s:：、.．]+", "", value).lower()


def _heading_key(value: str):
    match = TOP_KEY.match(value.strip())
    return match.group(1) if match else None


def _heading_match(line: str, title: str):
    normalized = _normalize(line).split("/", 1)[0]
    wanted = _normalize(title).split("/", 1)[0]
    wanted_core = re.sub(r"(?:与|及)?步骤$", "", wanted)
    return (normalized == wanted or wanted in normalized or normalized in wanted
            or normalized == wanted_core or normalized.startswith(wanted_core))


def _section_excerpt(text: str, title: str):
    lines = _clean_lines(text)
    wanted_key = _heading_key(title)
    start = None
    for index, line in enumerate(lines):
        if _heading_match(line, title):
            start = index + 1
            break
    if start is None:
        return []
    selected = []
    for line in lines[start:]:
        if HEADING.match(line):
            current_key = _heading_key(line)
            if wanted_key and current_key == wanted_key:
                continue
            if wanted_key and not wanted_key.isdigit() and current_key and current_key.isdigit():
                selected.append(line)
                continue
            break
        selected.append(line)
    return selected


def _paragraphs(lines):
    groups, current = [], []
    for line in lines:
        if FORMULA_LINE.match(line.replace(" ", "")):
            if current:
                groups.append({"type": "paragraph", "text": "".join(current)})
                current = []
            groups.append({"type": "formula", "text": line})
        else:
            current.append(line)
            if line.endswith(("。", "！", "？", ".", "!", "?")):
                groups.append({"type": "paragraph", "text": "".join(current)})
                current = []
    if current:
        groups.append({"type": "paragraph", "text": "".join(current)})
    return groups


def scaffold(inventory_path: Path, report_path: Path | None = None, refresh=False):
    inventory_path = inventory_path.expanduser().resolve()
    inventory = fastgen.load(inventory_path)
    report_path = (report_path or inventory_path.parent / "report.json").expanduser().resolve()
    report = fastgen.load(report_path)
    sources = []
    for item in inventory.get("files", []):
        if item.get("role") not in {"guide", "template"} or not item.get("extracted_text"):
            continue
        source_path = Path(item["path"])
        if not source_path.is_file() or fastgen.sha256(source_path) != item.get("sha256"):
            raise ValueError(f"Source changed after inventory: {source_path}")
        text_path = Path(item["extracted_text"])
        if text_path.is_file():
            expected = item.get("extracted_text_sha256")
            if expected and fastgen.sha256(text_path) != expected:
                raise ValueError(f"Extracted source text changed: {text_path}")
            sources.append((item, text_path.read_text(encoding="utf-8")))
    evidence = []
    filled = 0
    for section in report.get("sections", []):
        title = str(section.get("title", "")).strip()
        candidates = []
        for item, text in sources:
            lines = _section_excerpt(text, title)
            if lines:
                candidates.append({
                    "source": item["path"], "source_sha256": item["sha256"],
                    "lines": lines, "structured_manifest": item.get("structured_manifest"),
                })
        chosen = candidates[0] if candidates else None
        existing = section.get("blocks", [])
        if chosen and (refresh or not existing):
            section["blocks"] = _paragraphs(chosen["lines"])
            filled += 1
        evidence.append({
            "section": title, "matched": bool(chosen), "candidates": candidates,
            "selected_source": chosen["source"] if chosen else None,
            "draft_block_count": len(section.get("blocks", [])),
            "review_required": True,
        })
    report["draft_status"] = "source-extract-needs-rewrite-and-verification"
    report["draft_brief"] = str((inventory_path.parent / "draft-brief.json").resolve())
    fastgen.dump(report_path, report)
    related = []
    for item in inventory.get("files", []):
        manifest_path = item.get("structured_manifest")
        if not manifest_path or not Path(manifest_path).is_file():
            continue
        manifest = fastgen.load(manifest_path)
        page_counts = {}
        for asset in manifest.get("assets", []):
            pages = asset.get("pages") or ([asset["page"]] if asset.get("page") else [])
            for page in pages:
                page_counts[str(page)] = page_counts.get(str(page), 0) + 1
        related.append({
            "source": item["path"], "structured_manifest": manifest_path,
            "tables": manifest.get("tables", []),
            "asset_count": len(manifest.get("assets", [])), "assets_by_page": page_counts,
            "needs_ocr": manifest.get("needs_ocr", False),
        })
    brief = {
        "version": VERSION, "status": "needs-content-review",
        "inventory": str(inventory_path), "inventory_sha256": fastgen.sha256(inventory_path),
        "report": str(report_path), "sections": evidence, "related_materials": related,
        "instructions": [
            "Rewrite source excerpts in the student's own report structure.",
            "Verify every formula, symbol, unit, table, figure, and measurement against its source.",
            "Do not treat unmatched sections or extracted expectations as observed results.",
        ],
    }
    brief_path = inventory_path.parent / "draft-brief.json"
    fastgen.dump(brief_path, brief)
    return {
        "status": brief["status"], "report": str(report_path), "brief": str(brief_path),
        "sections": len(evidence), "filled_sections": filled,
        "unmatched_sections": [item["section"] for item in evidence if not item["matched"]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(scaffold(args.inventory, args.report, args.refresh),
                         ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"draft_report: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
