#!/usr/bin/env python3
"""Tests for check_limits. Run with: python -m pytest -q   (or python test_check_limits.py)"""

from check_limits import FAIL, NOTE, PASS, bar_area, evaluate


def test_max_rule_passes_below_limit():
    result = evaluate("A", value=0.37, limit=0.85, rule="max")
    assert result.status == PASS
    assert result.margin > 0


def test_max_rule_fails_above_limit():
    result = evaluate("A", value=0.91, limit=0.85, rule="max")
    assert result.status == FAIL
    assert result.margin < 0


def test_min_rule_passes_above_limit():
    result = evaluate("B", value=1140, limit=375, rule="min")
    assert result.status == PASS


def test_min_rule_fails_below_limit():
    result = evaluate("B", value=221.18, limit=375, rule="min")
    assert result.status == FAIL


def test_bar_area_three_bars_of_22mm():
    # 3 * pi * 11^2 = 1140.4 mm2
    assert abs(bar_area("3C22") - 1140.4) < 0.1


def test_bar_area_handles_spacing_and_blank():
    assert bar_area("") is None
    assert bar_area(None) is None
    assert bar_area("garbage") is None


def test_note_is_not_a_failure():
    assert NOTE != FAIL and NOTE != PASS


if __name__ == "__main__":
    failures = 0
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                print(f"PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
    raise SystemExit(1 if failures else 0)
