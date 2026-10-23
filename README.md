# structural-check

A small Python tool that checks structural design values against the code limits they have to satisfy, and reports pass or fail with the margin left in hand.

Built out of a real problem: the beam reinforcement schedule in my final-year building design ran to 75 sections, each with a required steel area and a minimum steel area. Checking them one row at a time is slow, easy to get wrong, and impossible to prove afterwards that nothing was missed.

## What it checks

| Check | Rule | Rows |
|---|---|---|
| Column axial compression ratio | `value <= 0.85` (grade 3 seismic) | 4 |
| Inter-storey drift angle | `value <= 1/550` | 5 |
| Beam steel provided vs required | `As_provided >= As_req` | 75 |
| Beam steel required vs minimum | `As_req >= As_min` | 75 |

Every row carries its own value *and* its own limit, so the output is auditable — you can point at any line and say which criterion it was checked against.

## Run it

```bash
python check_limits.py
```

Writes a full report to `output/report.txt` and exits with status 1 if anything failed, so it can be dropped into CI.

```bash
python test_check_limits.py     # 7 tests, no dependencies
```

No third-party packages. Standard library only.

## Three decisions worth explaining

**1. Pass/fail is per row, not per project.**
A single "the design is fine" result tells you nothing about which check passed and why. Every row reports its own status and margin, so a reviewer can disagree with a specific line.

**2. `As_req < As_min` is not a failure.**
It means the section is governed by minimum reinforcement rather than by bending. Reporting it as a failure would be wrong engineering; reporting it as nothing would hide a number that looks odd. It gets its own status (`NOTE`) so the reader knows why the value is small.

**3. The detailing notation is parsed, not ignored.**
Most rows leave the provided-steel-area column blank, but every row states the bars (`3C22`). The tool converts that to an area — 3 × π × 11² = 1140 mm² — so the provided-vs-required check runs on all 75 sections instead of the 5 where the column happened to be filled in. Silently skipping rows is how a check quietly stops being a check.

## Data

`data/` holds values exported from the calculation record of a five-storey reinforced concrete frame office building (Suizhou, Hubei) — a final-year design project. The numbers are the project's own; the checking was previously done by hand.

## Limitations

- Limits are read per row, so a code revision means editing the data, not the code.
- Only the checks listed above are implemented — this is not a design tool and does not replace one.
- No unit conversion; the CSV must be in the units the headers state (mm, mm², kN, MPa).
