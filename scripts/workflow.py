#!/usr/bin/env python3
"""Inventory inputs, build a DOCX, render previews, and gate delivery on review."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from docx import Document
from PIL import Image
from pypdf import PdfReader

import fastgen

HEAD = re.compile(r"^(?:[一二三四五六七八九十]+|\d+)[、.．]\s*\S+")
FIGURE = re.compile(r"(?:图|Fig\.?)\s*\d+[\w.-]*", re.IGNORECASE)
TABLE = re.compile(r"(?:表|Table)\s*\d+[\w.-]*", re.IGNORECASE)
PLACEHOLDER = re.compile(r"\{\{[^{}]+\}\}")


def document_text(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages), len(pages), sum(len(page.images) for page in reader.pages)
    if suffix == ".docx":
        doc = Document(path)
        content = [p.text for p in fastgen.paragraphs(doc)]
        return "\n".join(content), None, len(doc.inline_shapes)
    if suffix in {".txt", ".md", ".csv", ".tsv"}:
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                return path.read_text(encoding=encoding), None, 0
            except UnicodeDecodeError:
                pass
        raise ValueError(f"Cannot decode source text: {path}")
    return "", None, 0


def record(path: Path, role: str, text_dir: Path, index: int):
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    item = {
        "role": role, "path": str(path), "name": path.name,
        "size_bytes": path.stat().st_size, "sha256": fastgen.sha256(path),
    }
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        with Image.open(path) as image:
            item["dimensions"] = list(image.size)
        item["visual_review_required"] = True
    else:
        content, page_count, image_count = document_text(path)
        item.update({
            "pages": page_count, "embedded_images": image_count,
            "characters": len(content),
            "figure_mentions": sorted(set(FIGURE.findall(content))),
            "table_mentions": sorted(set(TABLE.findall(content))),
        })
        if content:
            text_dir.mkdir(parents=True, exist_ok=True)
            text_path = text_dir / f"{index:02d}-{role}.txt"
            text_path.write_text(content, encoding="utf-8")
            item["extracted_text"] = str(text_path.resolve())
        if role == "template" and path.suffix.lower() == ".docx":
            item["headings"] = [line.strip() for line in content.splitlines() if HEAD.match(line.strip())]
            item["placeholders"] = sorted(set(PLACEHOLDER.findall(content)))
    return item


def prepare(workdir: Path, guides, template, images, data, sections, scope):
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    files = []
    paths = ([("guide", p) for p in guides] +
             ([("template", template)] if template else []) +
             [("image", p) for p in images] +
             [("data", p) for p in data])
    if not paths:
        raise ValueError("Provide at least one guide, template, image, or data file.")
    if template and Path(template).suffix.lower() != ".docx":
        raise ValueError("The template must be DOCX; convert old DOC files before prepare.")
    for index, (role, path) in enumerate(paths, 1):
        files.append(record(Path(path), role, workdir / "source-text", index))
    chosen = list(sections)
    if not chosen:
        template_item = next((item for item in files if item["role"] == "template"), {})
        chosen = template_item.get("headings", [])
    inventory = {
        "scope": scope, "requested_sections": list(sections),
        "files": files,
        "needs_human_or_agent_review": [
            "Confirm requested sections and draft content against the guide.",
            "Select only relevant, clear images and verify they have no watermark.",
            "Verify formula symbols, units, tables, and all real measurements.",
        ],
    }
    inventory_path = workdir / "inventory.json"
    fastgen.dump(inventory_path, inventory)
    spec_path = workdir / "report.json"
    if not spec_path.exists():
        fastgen.dump(spec_path, {
            "title": "大学物理实验报告",
            "metadata": {},
            "sections": [
                {"title": title, "anchor": title, "blocks": []} for title in chosen
            ],
        })
    return {"inventory": str(inventory_path), "draft_spec": str(spec_path),
            "files": len(files), "sections": len(chosen)}


def validate_spec(spec: dict, base: Path, required_sections):
    sections = spec.get("sections", [])
    if not sections:
        raise ValueError("Report JSON has no sections; complete the draft first.")
    names = [str(section.get("title", "")).strip() for section in sections]
    if any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError("Section titles must be nonempty and unique.")
    if required_sections and names != required_sections:
        raise ValueError("Report sections do not match the requested scope and order.")
    counts = {"figure": 0, "table": 0, "formula": 0}
    for section in sections:
        blocks = section.get("blocks", [])
        if not blocks:
            raise ValueError(f"Section has no content: {section['title']}")
        for block in blocks:
            kind = block.get("type", "paragraph")
            if kind == "paragraph":
                content = block.get("text") or "".join(x.get("text", "") for x in block.get("segments", []))
                if not str(content).strip():
                    raise ValueError(f"Empty paragraph in {section['title']}")
            elif kind == "formula":
                if not str(block.get("text", "")).strip():
                    raise ValueError(f"Empty formula in {section['title']}")
                counts[kind] += 1
            elif kind == "figure":
                path = Path(block.get("path", ""))
                path = path if path.is_absolute() else base / path
                if not path.is_file() or not str(block.get("caption", "")).strip():
                    raise ValueError(f"Figure needs an existing file and caption: {section['title']}")
                counts[kind] += 1
            elif kind == "table":
                if not block.get("columns") or not str(block.get("caption", "")).strip():
                    raise ValueError(f"Table needs columns and caption: {section['title']}")
                counts[kind] += 1
            elif kind != "page_break":
                raise ValueError(f"Unsupported block: {kind}")
    return counts


def find_soffice():
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    for candidate in (
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def render(docx_path: Path, preview_dir: Path, pdf_path=None, renderer="auto"):
    preview_dir.mkdir(parents=True, exist_ok=True)
    if pdf_path:
        pdf_path = Path(pdf_path).resolve()
        if not pdf_path.is_file():
            raise FileNotFoundError(pdf_path)
    elif renderer != "none":
        soffice = find_soffice()
        if not soffice:
            return None, []
        profile = (preview_dir / "libreoffice-profile").resolve().as_uri()
        subprocess.run([
            soffice, "--headless", f"-env:UserInstallation={profile}",
            "--convert-to", "pdf", "--outdir", str(preview_dir), str(docx_path)
        ], check=True, capture_output=True, text=True, timeout=120)
        pdf_path = preview_dir / (docx_path.stem + ".pdf")
        if not pdf_path.is_file():
            raise RuntimeError("LibreOffice did not create a PDF.")
    else:
        return None, []
    if pdf_path.stat().st_mtime < docx_path.stat().st_mtime - 2:
        raise ValueError("The supplied PDF predates the DOCX; export the latest report again.")
    count = len(PdfReader(pdf_path).pages)
    if count == 0:
        raise ValueError("Rendered PDF has no pages.")
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return pdf_path, []
    for old_preview in preview_dir.glob("page-*.png"):
        old_preview.unlink()
    prefix = preview_dir / "page"
    subprocess.run([
        pdftoppm, "-f", "1", "-l", str(count), "-r", "120",
        "-png", str(pdf_path), str(prefix)
    ], check=True, capture_output=True, text=True, timeout=120)
    previews = sorted(preview_dir.glob("page-*.png"), key=lambda path: int(path.stem.split("-")[-1]))
    if len(previews) != count:
        raise RuntimeError(f"Expected {count} page previews, got {len(previews)}.")
    return pdf_path, previews


def run(workdir: Path, spec_path=None, template=None, output=None, pdf=None, renderer="auto"):
    workdir = workdir.resolve()
    inventory_path = workdir / "inventory.json"
    inventory = fastgen.load(inventory_path) if inventory_path.is_file() else {}
    spec_path = Path(spec_path or workdir / "report.json").resolve()
    spec = fastgen.load(spec_path)
    counts = validate_spec(spec, spec_path.parent, inventory.get("requested_sections", []))
    if template is None:
        template_item = next((x for x in inventory.get("files", []) if x["role"] == "template"), None)
        template = Path(template_item["path"]) if template_item else None
    output = Path(output or workdir / "output" / "report.docx").resolve()
    template_hash = fastgen.sha256(template) if template else None
    template_images = len(Document(template).inline_shapes) if template else 0
    template_math = len(Document(template).element.xpath(".//m:oMath")) if template else 0
    qa = fastgen.build(spec_path, output, template)
    if template and fastgen.sha256(template) != template_hash:
        raise RuntimeError("Source template changed during build.")
    for key, actual_key, baseline in (("figure", "inline_images", template_images),
                                      ("formula", "native_math_objects", template_math)):
        actual = qa[actual_key] - baseline
        if actual != counts[key]:
            qa["status"] = "needs-fix"
            qa.setdefault("count_mismatch", {})[key] = {"expected": counts[key], "actual": actual}
    if qa["table_blocks"] != counts["table"]:
        qa["status"] = "needs-fix"
    fastgen.dump(output.with_suffix(".qa.json"), qa)
    if qa["status"] != "pass":
        raise RuntimeError(f"Structural QA failed: {output.with_suffix('.qa.json')}")
    pdf_path, previews = render(output, workdir / "preview", pdf, renderer)
    review = {
        "status": "needs-visual-review" if previews else "render-unavailable",
        "docx": str(output), "docx_sha256": fastgen.sha256(output),
        "pdf": str(pdf_path) if pdf_path else None,
        "criteria": ["scope", "cover", "no_watermark", "page_layout", "figures",
                     "tables", "formula_symbols", "units", "captions"],
        "pages": [
            {"page": i, "preview": str(path), "status": "pending", "notes": ""}
            for i, path in enumerate(previews, 1)
        ],
    }
    review_path = workdir / "review.json"
    fastgen.dump(review_path, review)
    return {"status": review["status"], "docx": str(output), "qa": str(output.with_suffix(".qa.json")),
            "review": str(review_path), "pages": len(previews)}


def finalize(workdir: Path):
    workdir = workdir.resolve()
    review = fastgen.load(workdir / "review.json")
    docx = Path(review["docx"])
    qa = fastgen.load(docx.with_suffix(".qa.json"))
    if qa["status"] != "pass" or fastgen.sha256(docx) != review["docx_sha256"]:
        raise ValueError("DOCX changed after QA or structural QA did not pass; run again.")
    pages = review.get("pages", [])
    if (not pages or
        [page.get("page") for page in pages] != list(range(1, len(pages) + 1)) or
        any(page.get("status") != "pass" or not Path(page.get("preview", "")).is_file()
            for page in pages)):
        raise ValueError("Inspect every rendered page and set each page status to pass before finalizing.")
    result = {"status": "pass", "docx": str(docx), "pdf": review.get("pdf"),
              "pages_reviewed": len(pages), "qa": str(docx.with_suffix(".qa.json"))}
    fastgen.dump(workdir / "delivery.json", result)
    return result


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="Inventory materials and create a blank report JSON")
    p.add_argument("--workdir", type=Path, required=True)
    p.add_argument("--guide", action="append", type=Path, default=[])
    p.add_argument("--template", type=Path)
    p.add_argument("--image", action="append", type=Path, default=[])
    p.add_argument("--data", action="append", type=Path, default=[])
    p.add_argument("--section", action="append", default=[])
    p.add_argument("--scope", default="")
    p = sub.add_parser("run", help="Build, structurally check, and render page previews")
    p.add_argument("--workdir", type=Path, required=True)
    p.add_argument("--spec", type=Path)
    p.add_argument("--template", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--pdf", type=Path, help="Use a PDF already exported from this DOCX")
    p.add_argument("--renderer", choices=("auto", "none"), default="auto")
    p = sub.add_parser("finalize", help="Verify page-by-page review and mark delivery ready")
    p.add_argument("--workdir", type=Path, required=True)
    return parser.parse_args()


def main():
    args = cli()
    try:
        if args.command == "prepare":
            result = prepare(args.workdir, args.guide, args.template, args.image,
                             args.data, args.section, args.scope)
        elif args.command == "run":
            result = run(args.workdir, args.spec, args.template, args.output, args.pdf, args.renderer)
        else:
            result = finalize(args.workdir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"workflow: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
