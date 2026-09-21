#!/usr/bin/env python3
"""Prepare source photos and generate reproducible plots or schematic figures."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageOps

import fastgen


def _different_source(source: Path, output: Path):
    source, output = source.resolve(), output.resolve()
    if source == output:
        raise ValueError("Output must differ from the source image.")
    if not source.is_file():
        raise FileNotFoundError(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    return source, output


def _deskew_angle(image: Image.Image):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Auto-deskew needs OpenCV; install requirements-ocr.txt.") from exc
    gray = np.array(image.convert("L"))
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    lines = cv2.HoughLinesP(binary, 1, math.pi / 180, 80,
                            minLineLength=max(40, gray.shape[1] // 5),
                            maxLineGap=20)
    if lines is None:
        raise ValueError("No reliable table lines found for auto-deskew.")
    angles = []
    for line in lines[:, 0]:
        x1, y1, x2, y2 = map(int, line)
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if abs(angle) <= 15:
            angles.append(angle)
    if not angles:
        raise ValueError("No near-horizontal table lines found for auto-deskew.")
    return float(np.median(angles))


def preprocess(source: Path, output: Path, crop=None, rotate=0.0,
               deskew=False, grayscale=False, autocontrast=False):
    source, output = _different_source(source, output)
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
    operations = ["exif_orientation"]
    if crop:
        x1, y1, x2, y2 = crop
        if not (0 <= x1 < x2 <= image.width and 0 <= y1 < y2 <= image.height):
            raise ValueError("Crop must lie within the original image.")
        image = image.crop((x1, y1, x2, y2))
        operations.append({"crop": crop})
    if rotate:
        image = image.rotate(float(rotate), expand=True, fillcolor="white")
        operations.append({"rotate_degrees": float(rotate)})
    if deskew:
        angle = _deskew_angle(image)
        image = image.rotate(angle, expand=True, fillcolor="white")
        operations.append({"auto_deskew_degrees": angle})
    if grayscale:
        image = image.convert("L")
        operations.append("grayscale")
    if autocontrast:
        image = ImageOps.autocontrast(image)
        operations.append("autocontrast")
    image.save(output)
    manifest = {
        "kind": "preprocessed_source", "source": str(source),
        "source_sha256": fastgen.sha256(source), "output": str(output),
        "output_sha256": fastgen.sha256(output), "operations": operations,
        "requires_visual_review": True,
    }
    fastgen.dump(output.with_suffix(".image.json"), manifest)
    return manifest


def plot_fit(analysis_path: Path, fit_id: str, output: Path, title=""):
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = output.with_suffix(".figure.json")
    import analyze_data
    report = analyze_data.check_analysis(analysis_path)
    analysis_hash = fastgen.sha256(analysis_path)
    if manifest_path.is_file() and output.is_file():
        cached = fastgen.load(manifest_path)
        if (cached.get("source_analysis_sha256") == analysis_hash
                and cached.get("fit_id") == fit_id
                and cached.get("title", "") == title
                and cached.get("output_sha256") == fastgen.sha256(output)):
            cached["cache_hit"] = True
            return cached
    mpl_cache = output.parent / ".matplotlib-cache"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Plotting needs requirements-analysis.txt.") from exc
    fit = report["results"].get(fit_id)
    if not fit or fit["type"] != "linear_fit":
        raise ValueError(f"Unknown linear-fit result: {fit_id}")
    source = Path(fit["residuals_csv"])
    frame = pd.read_csv(source)
    x_name, y_name = fit["x"], fit["y"]
    x, y = frame[x_name], frame[y_name]
    ordered = frame.sort_values(x_name)
    x_unit = fastgen.load(report["config"]).get("units", {}).get(x_name, "dimensionless")
    y_unit = fit["intercept"]["unit"]
    fig, (ax, residual_ax) = plt.subplots(
        2, 1, figsize=(6.3, 5.4), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
        constrained_layout=True,
    )
    ax.scatter(x, y, s=24, color="#1261a0", label="Measured")
    ax.plot(ordered[x_name], ordered["predicted"], color="#c23b22",
            label=f"Fit ($R^2$={fit['r_squared']:.4f})")
    ax.set_ylabel(f"{y_name} / {y_unit}")
    ax.set_title(title or f"{y_name} vs {x_name}")
    ax.grid(alpha=0.25)
    ax.legend()
    residual_ax.scatter(x, frame["residual"], s=18, color="#1261a0")
    residual_ax.axhline(0, color="#777777", linewidth=1)
    residual_ax.set_xlabel(f"{x_name} / {x_unit}")
    residual_ax.set_ylabel(f"Residual / {y_unit}")
    residual_ax.grid(alpha=0.25)
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    manifest = {
        "kind": "data_plot", "source_analysis": str(analysis_path.resolve()),
        "source_analysis_sha256": fastgen.sha256(analysis_path),
        "fit_id": fit_id, "title": title, "output": str(output),
        "output_sha256": fastgen.sha256(output),
        "cache_hit": False,
    }
    fastgen.dump(manifest_path, manifest)
    return manifest


def schematic(spec_path: Path, output: Path):
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    mpl_cache = output.parent / ".matplotlib-cache"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    try:
        import schemdraw
        import schemdraw.elements as elm
    except ImportError as exc:
        raise RuntimeError("Schematic generation needs schemdraw.") from exc
    spec_path = spec_path.resolve()
    spec = fastgen.load(spec_path)
    components = spec.get("components", [])
    if not components:
        raise ValueError("Schematic requires explicit components.")
    classes = {
        "resistor": elm.Resistor, "capacitor": elm.Capacitor,
        "inductor": elm.Inductor, "source_v": elm.SourceV,
        "diode": elm.Diode, "line": elm.Line, "ground": elm.Ground,
    }
    directions = {"right", "left", "up", "down"}
    schemdraw.use("matplotlib")
    drawing = schemdraw.Drawing(show=False)
    for item in components:
        kind = item.get("type")
        if kind not in classes:
            raise ValueError(f"Unsupported schematic component: {kind}")
        element = classes[kind]()
        direction = item.get("direction", "right")
        if direction not in directions:
            raise ValueError(f"Unsupported direction: {direction}")
        element = getattr(element, direction)()
        if item.get("label"):
            element = element.label(str(item["label"]))
        drawing.add(element)
    drawing.save(str(output), dpi=220)
    manifest = {
        "kind": "schematic", "source_spec": str(spec_path),
        "source_spec_sha256": fastgen.sha256(spec_path),
        "output": str(output), "output_sha256": fastgen.sha256(output),
        "requires_visual_review": True,
    }
    fastgen.dump(output.with_suffix(".figure.json"), manifest)
    return manifest


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("preprocess")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--crop", type=int, nargs=4)
    p.add_argument("--rotate", type=float, default=0)
    p.add_argument("--deskew", action="store_true")
    p.add_argument("--grayscale", action="store_true")
    p.add_argument("--autocontrast", action="store_true")
    p = sub.add_parser("plot")
    p.add_argument("--analysis", type=Path, required=True)
    p.add_argument("--fit-id", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--title", default="")
    p = sub.add_parser("schematic")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main():
    args = cli()
    try:
        if args.command == "preprocess":
            result = preprocess(args.input, args.output, args.crop, args.rotate,
                                args.deskew, args.grayscale, args.autocontrast)
        elif args.command == "plot":
            result = plot_fit(args.analysis, args.fit_id, args.output, args.title)
        else:
            result = schematic(args.spec, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"figure_tools: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
