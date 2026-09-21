#!/usr/bin/env python3
"""Single command entry point for the standalone FastGen report toolkit."""
from __future__ import annotations

import importlib
import sys

VERSION = "0.3.0"
WORKFLOW_COMMANDS = {"start", "prepare", "run", "preview", "finalize", "preflight"}
MODULE_COMMANDS = {
    "ingest": "material_ingest",
    "ocr": "table_ocr",
    "data": "analyze_data",
    "figures": "figure_tools",
    "template": "template_profile",
    "patch": "docx_patch",
    "draft": "draft_report",
    "review": "review_dashboard",
    "benchmark": "benchmark",
}


def usage():
    return """Physics Lab Report FastGen

Usage:
  labfast.py preflight|start|prepare|run|preview|finalize [options]
  labfast.py ingest [options]
  labfast.py ocr extract|verify [options]
  labfast.py data plan|run|check [options]
  labfast.py figures preprocess|plot|schematic [options]
  labfast.py template create|check [options]
  labfast.py patch --spec patch.json
  labfast.py draft --inventory work/inventory.json
  labfast.py review build|serve|apply [options]
  labfast.py benchmark --input guide.pdf --output-dir work/benchmark

Run a command with --help for its detailed options.
"""


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print(usage())
        return 0
    if argv[0] == "--version":
        print(VERSION)
        return 0
    command, rest = argv[0], argv[1:]
    if command in WORKFLOW_COMMANDS:
        module_name, delegated, program = "workflow", [command, *rest], "labfast"
    elif command in MODULE_COMMANDS:
        module_name, delegated, program = MODULE_COMMANDS[command], rest, f"labfast {command}"
    else:
        print(f"Unknown command: {command}\n\n{usage()}", file=sys.stderr)
        return 2
    module = importlib.import_module(module_name)
    previous = sys.argv
    try:
        sys.argv = [program, *delegated]
        return module.main()
    finally:
        sys.argv = previous


if __name__ == "__main__":
    raise SystemExit(main())
