#!/usr/bin/env python3
"""Measure cold and cached FastGen operations without changing source materials."""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import fastgen
import material_ingest


def benchmark_ingest(source: Path, output_dir: Path, runs=3, backend="fast"):
    source = source.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if runs < 2 or runs > 20:
        raise ValueError("Use between 2 and 20 benchmark runs.")
    samples = []
    for index in range(runs):
        started = time.perf_counter()
        result = material_ingest.ingest(
            source, output_dir / "material", force=index == 0, backend=backend)
        samples.append({
            "run": index + 1, "milliseconds": round((time.perf_counter() - started) * 1000, 3),
            "cache_hit": result["cache_hit"], "backend": result["backend"],
        })
    cold = samples[0]["milliseconds"]
    warm_values = [item["milliseconds"] for item in samples[1:]]
    warm_mean = sum(warm_values) / len(warm_values)
    warm_median = statistics.median(warm_values)
    report = {
        "status": "pass", "kind": "material_ingest",
        "source": str(source), "source_sha256": fastgen.sha256(source),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "samples": samples, "cold_ms": cold,
        "warm_mean_ms": round(warm_mean, 3), "warm_median_ms": round(warm_median, 3),
        "speedup_mean": round(cold / warm_mean, 2) if warm_mean else None,
        "speedup_median": round(cold / warm_median, 2) if warm_median else None,
    }
    path = output_dir / "benchmark.json"
    fastgen.dump(path, report)
    return {**report, "benchmark": str(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--backend", choices=("fast", "auto", "docling"), default="fast")
    args = parser.parse_args()
    try:
        print(json.dumps(benchmark_ingest(args.input, args.output_dir, args.runs, args.backend),
                         ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"benchmark: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
