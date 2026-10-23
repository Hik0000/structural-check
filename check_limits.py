#!/usr/bin/env python3
"""
Code-compliance checker for structural design outputs.

Reads design values from CSV, compares each one against the limit it has to
satisfy, and reports pass / fail with the remaining margin. Built to replace
row-by-row manual checking of a 75-row beam reinforcement schedule, where a
single missed row is easy to miss and hard to prove you did not miss.

Every row carries its own value and its own limit, so the output is auditable:
you can point at any line and say which criterion it was checked against.

Usage:
    python check_limits.py
    python check_limits.py --data data --out output/report.txt
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path

PASS = "PASS"
FAIL = "FAIL"
NOTE = "NOTE"  # not a failure, but the row deserves a human look


@dataclass
class Result:
    key: str
    value: float
    limit: float
    status: str
    margin: float  # fraction of the limit still in hand; negative = exceeded


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def to_float(raw: str | None) -> float | None:
    """Parse a cell, tolerating blanks and stray whitespace."""
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def bar_area(notation: str | None) -> float | None:
    """Turn a detailing notation such as "3C22" into a steel area in mm2.

    "3C22" means three bars of 22 mm diameter: 3 * pi * (22/2)^2 = 1140 mm2.
    The letter is the steel grade (C = HRB400) and does not affect the area,
    so it is matched but ignored.
    """
    if not notation:
        return None
    match = re.fullmatch(r"\s*(\d+)\s*[A-Za-z]?\s*(\d+)\s*", notation)
    if not match:
        return None
    count, diameter = int(match.group(1)), int(match.group(2))
    return count * math.pi * (diameter / 2) ** 2


def evaluate(key: str, value: float, limit: float, rule: str) -> Result:
    """Compare one value against one limit.

    rule="max": value must stay at or below the limit (e.g. axial ratio <= 0.85)
    rule="min": value must reach at least the limit (e.g. As >= As_min)
    """
    if rule == "max":
        ok = value <= limit
        margin = (limit - value) / limit if limit else 0.0
    else:
        ok = value >= limit
        margin = (value - limit) / limit if limit else 0.0
    return Result(key, value, limit, PASS if ok else FAIL, margin)


def check_axial_ratio(rows: list[dict[str, str]]) -> list[Result]:
    """Column axial compression ratio against the code limit (0.85 for grade 3)."""
    results = []
    for row in rows:
        value = to_float(row.get("axial_ratio"))
        limit = to_float(row.get("limit"))
        if value is None or limit is None:
            continue
        results.append(evaluate(row.get("member", "?"), value, limit, "max"))
    return results


def check_drift(rows: list[dict[str, str]]) -> list[Result]:
    """Inter-storey drift angle against the 1/550 limit."""
    results = []
    for row in rows:
        value = to_float(row.get("theta"))
        limit = to_float(row.get("limit_theta"))
        if value is None or limit is None:
            continue
        key = f"storey {row.get('storey', '?')}"
        results.append(evaluate(key, value, limit, "max"))
    return results


def check_beam_reinforcement(rows: list[dict[str, str]]) -> tuple[list[Result], list[Result]]:
    """Beam reinforcement: provided area vs required, and required vs minimum.

    Two separate questions:
      1. Is the steel actually detailed (As_provided) at least what the design
         demanded (As_req)?  This is a real pass/fail.
      2. Is As_req below As_min?  That is not an error - it means the section is
         governed by minimum reinforcement rather than by bending.  Flagged as
         NOTE so the reader knows why the number looks small.
    """
    provided_vs_required: list[Result] = []
    required_vs_minimum: list[Result] = []

    for row in rows:
        key = f"{row.get('storey', '?')}F {row.get('span', '?')} {row.get('section', '?')}"
        required = to_float(row.get("As_req_mm2"))
        minimum = to_float(row.get("As_min_mm2"))
        provided = to_float(row.get("As_provided_mm2"))
        if provided is None:
            # Most rows leave the provided-area column blank; derive it from the
            # detailing notation instead of silently dropping the row.
            provided = bar_area(row.get("bars"))

        if required is not None and minimum is not None:
            result = evaluate(key, required, minimum, "min")
            if result.status == FAIL:
                result.status = NOTE
            required_vs_minimum.append(result)

        if provided is not None and required is not None and required > 0:
            provided_vs_required.append(evaluate(key, provided, required, "min"))

    return provided_vs_required, required_vs_minimum


def render(title: str, rule_text: str, results: list[Result]) -> str:
    """One table per check, plus a one-line tally."""
    if not results:
        return f"\n[{title}]\n  rule: {rule_text}\n  no rows to check\n"

    lines = [f"\n[{title}]", f"  rule: {rule_text}", ""]
    width = max(12, max(len(r.key) for r in results))
    lines.append(f"    {'item'.ljust(width)}  {'value':>12}  {'limit':>12}  {'margin':>8}  status")
    lines.append(f"    {'-' * width}  {'-' * 12}  {'-' * 12}  {'-' * 8}  ------")
    for result in results:
        lines.append(
            f"    {result.key.ljust(width)}  {result.value:>12.6g}  {result.limit:>12.6g}  "
            f"{result.margin * 100:>7.1f}%  {result.status}"
        )

    passed = sum(1 for r in results if r.status == PASS)
    failed = sum(1 for r in results if r.status == FAIL)
    notes = sum(1 for r in results if r.status == NOTE)
    tally = f"  -> {len(results)} rows | {passed} pass | {failed} fail"
    if notes:
        tally += f" | {notes} note"
    lines.append(tally)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check structural design values against their code limits.")
    parser.add_argument("--data", default="data", type=Path, help="folder holding the CSV files")
    parser.add_argument("--out", default="output/report.txt", type=Path, help="where to write the report")
    args = parser.parse_args()

    axial = check_axial_ratio(read_csv(args.data / "column_axial_ratio.csv"))
    drift = check_drift(read_csv(args.data / "drift_wind.csv"))
    provided, minimum = check_beam_reinforcement(read_csv(args.data / "beam_reinforcement.csv"))

    body = "\n".join(
        [
            "Structural code-compliance check",
            "Project: five-storey RC frame office building, Suizhou (final year design)",
            "",
            render("1. Column axial compression ratio", "value <= limit", axial),
            render("2. Inter-storey drift angle", "value <= limit (1/550)", drift),
            render("3. Beam steel provided vs required", "As_provided >= As_req", provided),
            render("4. Beam steel required vs minimum", "As_req >= As_min (below = minimum-governed)", minimum),
        ]
    )

    everything = axial + drift + provided + minimum
    total = len(everything)
    failed = [r for r in everything if r.status == FAIL]
    noted = [r for r in everything if r.status == NOTE]

    summary = [
        "",
        "SUMMARY",
        f"  rows checked : {total}",
        f"  passed       : {total - len(failed) - len(noted)}",
        f"  failed       : {len(failed)}",
        f"  notes        : {len(noted)}",
    ]
    if failed:
        summary.append("")
        summary.append("  FAILURES")
        for result in failed:
            summary.append(f"    {result.key}: {result.value:g} vs limit {result.limit:g}")

    report = body + "\n".join(summary) + "\n"
    print(report)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"report written to {args.out}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
