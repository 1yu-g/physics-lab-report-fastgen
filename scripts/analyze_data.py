#!/usr/bin/env python3
"""Reproducible laboratory calculations from reviewed CSV data and an explicit plan."""
from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import operator
import re
import sys
from pathlib import Path

import fastgen
import table_ocr


def _assignments(values, cast=str):
    result = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"Expected COLUMN=VALUE: {value}")
        key, raw = value.split("=", 1)
        key = key.strip()
        if not key or key in result:
            raise ValueError(f"Duplicate or empty assignment: {value}")
        result[key] = cast(raw.strip())
    return result


def create_plan(input_path: Path, output: Path, summaries=None, x=None, y=None,
                fit_id="fit", units=None, type_b=None, ocr_review=None):
    input_path = input_path.expanduser().resolve()
    output = output.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if input_path.suffix.lower() not in {".csv", ".tsv"}:
        raise ValueError("Analysis plans require a CSV or TSV input table.")
    delimiter = "\t" if input_path.suffix.lower() == ".tsv" else ","
    with input_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream, delimiter=delimiter))
    if len(rows) < 2 or not rows[0]:
        raise ValueError("Input table needs a header and at least one data row.")
    columns = [str(value).strip() for value in rows[0]]
    if any(not value for value in columns) or len(columns) != len(set(columns)):
        raise ValueError("CSV column names must be nonempty and unique.")
    summaries = list(summaries or [])
    if len(summaries) != len(set(summaries)):
        raise ValueError("Summary columns must be unique.")
    operations = []
    type_b_values = _assignments(type_b, float)
    for summary_index, column in enumerate(summaries, 1):
        if column not in columns:
            raise ValueError(f"Column not found: {column}")
        suffix = re.sub(r"[^A-Za-z0-9_]", "_", column).strip("_") or str(summary_index)
        operation = {"id": f"summary_{suffix}", "type": "summary", "column": column}
        if column in type_b_values:
            operation["type_b"] = type_b_values[column]
        operations.append(operation)
    if bool(x) != bool(y):
        raise ValueError("Specify both --x and --y for a linear fit.")
    if x and y:
        if x not in columns or y not in columns:
            raise ValueError("Fit columns must exist in the input table.")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", fit_id):
            raise ValueError("Fit id must be an ASCII identifier for result placeholders.")
        operations.append({"id": fit_id, "type": "linear_fit", "x": x, "y": y})
    if not operations:
        raise ValueError("Add at least one --summary or an --x/--y fit pair.")
    unknown_type_b = set(type_b_values) - set(summaries)
    if unknown_type_b:
        raise ValueError(f"Type-B uncertainty has no matching summary: {sorted(unknown_type_b)}")
    output.parent.mkdir(parents=True, exist_ok=True)

    def portable(path):
        if path is None:
            return None
        path = Path(path).expanduser().resolve()
        try:
            return str(path.relative_to(output.parent))
        except ValueError:
            return str(path)

    unit_values = _assignments(units)
    unknown_units = set(unit_values) - set(columns)
    if unknown_units:
        raise ValueError(f"Units name unknown columns: {sorted(unknown_units)}")
    operation_ids = [item["id"] for item in operations]
    if len(operation_ids) != len(set(operation_ids)):
        raise ValueError("Generated operation ids collide; choose another --fit-id.")
    plan = {
        "input": portable(input_path),
        "units": unit_values,
        "operations": operations,
    }
    if ocr_review:
        if not Path(ocr_review).expanduser().is_file():
            raise FileNotFoundError(ocr_review)
        plan["ocr_review"] = portable(ocr_review)
    fastgen.dump(output, plan)
    return {
        "status": "pass", "plan": str(output), "columns": columns,
        "data_rows": len(rows) - 1, "operations": len(operations),
    }


def _dependencies():
    try:
        import pandas as pd
        import scipy
        import sympy as sp
        import pint
        import uncertainties
        from scipy import stats
        from uncertainties import ufloat
    except ImportError as exc:
        raise RuntimeError("Install requirements-analysis.txt before processing data.") from exc
    return pd, scipy, sp, pint, uncertainties, stats, ufloat


BINARY = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow,
}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_expression(expression: str, variables: dict):
    """Evaluate arithmetic only; calls, attributes, indexing, and code are rejected."""
    tree = ast.parse(expression, mode="eval")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name) and node.id in variables:
            return variables[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
            return BINARY[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
            return UNARY[type(node.op)](visit(node.operand))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "sqrt" and len(node.args) == 1
                and not node.keywords):
            return visit(node.args[0]) ** 0.5
        raise ValueError("Formula supports only named variables, numbers, + - * / ** and sqrt().")

    return visit(tree)


def _resolve_variable(item, results):
    if "from" not in item:
        if "value" not in item:
            raise ValueError("A formula variable needs value or from.")
        return {"value": float(item["value"]),
                "uncertainty": float(item.get("uncertainty", 0)),
                "unit": item.get("unit", "dimensionless")}
    parts = item["from"].split(".")
    if len(parts) != 2 or parts[0] not in results:
        raise ValueError(f"Invalid result reference: {item['from']}")
    value = results[parts[0]].get(parts[1])
    if not isinstance(value, dict) or "value" not in value:
        raise ValueError(f"Reference does not name a measured result: {item['from']}")
    return value


def _number_series(frame, name):
    if name not in frame.columns:
        raise ValueError(f"Column not found: {name}")
    import pandas as pd
    series = pd.to_numeric(frame[name], errors="raise")
    if series.isna().any() or not all(math.isfinite(float(x)) for x in series):
        raise ValueError(f"Column has blank or non-finite values: {name}")
    return series.astype(float)


def analyze(config_path: Path, output_dir: Path):
    config_path = config_path.expanduser().resolve()
    config = fastgen.load(config_path)
    source = Path(config["input"])
    source = source if source.is_absolute() else config_path.parent / source
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    review_path = None
    if config.get("ocr_review"):
        review_path = Path(config["ocr_review"])
        review_path = review_path if review_path.is_absolute() else config_path.parent / review_path
        review_path = review_path.resolve()
        table_ocr.check_verified(review_path, source)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cached_path = output_dir / "analysis.json"
    if cached_path.is_file():
        cached = fastgen.load(cached_path)
        expected_review_hash = fastgen.sha256(review_path) if review_path else None
        if (cached.get("input_sha256") == fastgen.sha256(source)
                and cached.get("config_sha256") == fastgen.sha256(config_path)
                and cached.get("ocr_review_sha256") == expected_review_hash):
            try:
                checked = check_analysis(cached_path)
            except (ValueError, FileNotFoundError, KeyError):
                pass
            else:
                return {"status": checked["status"], "analysis": str(cached_path),
                        "operations": len(checked["results"]), "cache_hit": True}
    pd, scipy, sp, pint, uncertainties, stats, ufloat = _dependencies()
    frame = pd.read_csv(source, encoding="utf-8-sig",
                        sep="\t" if source.suffix.lower() == ".tsv" else ",")
    if frame.empty:
        raise ValueError("Input table has no data rows.")
    units = config.get("units", {})
    registry = pint.UnitRegistry()
    results = {}
    for operation in config.get("operations", []):
        name = str(operation.get("id", "")).strip()
        if not name or name in results:
            raise ValueError("Every operation needs a unique nonempty id.")
        kind = operation.get("type")
        if kind == "summary":
            column = operation["column"]
            values = _number_series(frame, column)
            if len(values) < 2:
                raise ValueError("At least two values are needed for Type A uncertainty.")
            type_a = float(values.std(ddof=1) / math.sqrt(len(values)))
            type_b = float(operation.get("type_b", 0))
            if type_b < 0:
                raise ValueError("Type B standard uncertainty cannot be negative.")
            combined = math.hypot(type_a, type_b)
            unit = units.get(column, "dimensionless")
            results[name] = {
                "type": kind, "column": column, "n": len(values),
                "mean": {"value": float(values.mean()), "uncertainty": combined,
                         "unit": unit},
                "sample_std": float(values.std(ddof=1)),
                "type_a": type_a, "type_b": type_b,
            }
        elif kind == "linear_fit":
            x_name, y_name = operation["x"], operation["y"]
            x, y = _number_series(frame, x_name), _number_series(frame, y_name)
            if len(x) < 3 or x.nunique() < 2:
                raise ValueError("Linear fit needs at least three pairs and varied x.")
            fit = stats.linregress(x, y)
            if not all(math.isfinite(float(v)) for v in
                       (fit.slope, fit.intercept, fit.stderr, fit.intercept_stderr)):
                raise ValueError("Linear fit produced a non-finite result.")
            x_unit = units.get(x_name, "dimensionless")
            y_unit = units.get(y_name, "dimensionless")
            slope_unit = str((registry(y_unit) / registry(x_unit)).units)
            predicted = fit.slope * x + fit.intercept
            residuals_path = output_dir / f"{name}-residuals.csv"
            pd.DataFrame({
                x_name: x, y_name: y, "predicted": predicted,
                "residual": y - predicted,
            }).to_csv(residuals_path, index=False, encoding="utf-8-sig")
            results[name] = {
                "type": kind, "x": x_name, "y": y_name, "n": len(x),
                "slope": {"value": float(fit.slope),
                          "uncertainty": float(fit.stderr), "unit": slope_unit},
                "intercept": {"value": float(fit.intercept),
                              "uncertainty": float(fit.intercept_stderr),
                              "unit": y_unit},
                "r_squared": float(fit.rvalue ** 2),
                "residuals_csv": str(residuals_path),
                "residuals_sha256": fastgen.sha256(residuals_path),
            }
        elif kind == "formula":
            variable_specs = operation.get("variables", {})
            if not variable_specs:
                raise ValueError("Formula needs explicit variables.")
            values = {key: _resolve_variable(value, results)
                      for key, value in variable_specs.items()}
            quantities = {
                key: ufloat(value["value"], value.get("uncertainty", 0))
                * registry(value.get("unit", "dimensionless"))
                for key, value in values.items()
            }
            expression = operation["expression"]
            symbolic = safe_expression(
                expression, {key: sp.Symbol(key) for key in values})
            quantity = safe_expression(expression, quantities)
            if not hasattr(quantity, "units"):
                quantity = quantity * registry.dimensionless
            if operation.get("output_unit"):
                quantity = quantity.to(operation["output_unit"])
            magnitude = quantity.magnitude
            nominal = float(getattr(magnitude, "nominal_value", magnitude))
            uncertainty = float(getattr(magnitude, "std_dev", 0))
            if not math.isfinite(nominal) or not math.isfinite(uncertainty):
                raise ValueError(f"Formula produced a non-finite value: {name}")
            results[name] = {
                "type": kind, "expression": expression,
                "symbolic": str(symbolic), "latex": sp.latex(symbolic),
                "variables": values,
                "result": {"value": nominal, "uncertainty": uncertainty,
                           "unit": str(quantity.units)},
            }
        else:
            raise ValueError(f"Unsupported operation type: {kind}")
    if not results:
        raise ValueError("No analysis operations were specified.")
    output = {
        "status": "pass",
        "input": str(source), "input_sha256": fastgen.sha256(source),
        "config": str(config_path), "config_sha256": fastgen.sha256(config_path),
        "ocr_review": str(review_path) if review_path else None,
        "ocr_review_sha256": fastgen.sha256(review_path) if review_path else None,
        "versions": {
            "pandas": pd.__version__, "scipy": scipy.__version__,
            "sympy": sp.__version__, "pint": pint.__version__,
            "uncertainties": uncertainties.__version__,
        },
        "results": results,
    }
    path = output_dir / "analysis.json"
    fastgen.dump(path, output)
    return {"status": "pass", "analysis": str(path), "operations": len(results),
            "cache_hit": False}


def check_analysis(path: Path):
    report = fastgen.load(path)
    if report.get("status") != "pass":
        raise ValueError("Analysis status is not pass.")
    for filename, digest in (
        (report["input"], report["input_sha256"]),
        (report["config"], report["config_sha256"]),
    ):
        if not Path(filename).is_file() or fastgen.sha256(filename) != digest:
            raise ValueError(f"Analysis source changed: {filename}")
    if report.get("ocr_review"):
        review_path = Path(report["ocr_review"])
        if fastgen.sha256(review_path) != report["ocr_review_sha256"]:
            raise ValueError("OCR review changed after analysis.")
        table_ocr.check_verified(review_path, Path(report["input"]))
    for result in report["results"].values():
        if result["type"] == "linear_fit":
            path = Path(result["residuals_csv"])
            if not path.is_file() or fastgen.sha256(path) != result["residuals_sha256"]:
                raise ValueError("Fit residuals changed after analysis.")
    return report


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p = sub.add_parser("check")
    p.add_argument("--analysis", type=Path, required=True)
    p = sub.add_parser("plan", help="Create an explicit analysis plan from a reviewed table")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--ocr-review", type=Path)
    p.add_argument("--summary", action="append", default=[])
    p.add_argument("--type-b", action="append", default=[], metavar="COLUMN=VALUE")
    p.add_argument("--x")
    p.add_argument("--y")
    p.add_argument("--fit-id", default="fit")
    p.add_argument("--unit", action="append", default=[], metavar="COLUMN=UNIT")
    return parser.parse_args()


def main():
    args = cli()
    try:
        if args.command == "run":
            result = analyze(args.config, args.output_dir)
        elif args.command == "check":
            report = check_analysis(args.analysis)
            result = {"status": report["status"], "operations": len(report["results"])}
        else:
            result = create_plan(
                args.input, args.output, args.summary, args.x, args.y,
                args.fit_id, args.unit, args.type_b, args.ocr_review,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"analyze_data: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
