# Production Data Profile

Inspection date: 10 September 2026.

Source file: `data/production_data.csv`

This profile records what a normal pandas read found in the current synthetic extract. **The CSV was not changed.** The dataset is synthetic teaching data and intentionally contains errors so later validation can demonstrate how those problems are found. It contains no confidential production information.

The inspection tolerated mixed text and numbers. Non-numeric values were counted with `pandas.to_numeric(..., errors="coerce")` instead of crashing.

## Dataset overview

| Item | Result |
| --- | --- |
| File path | `data/production_data.csv` |
| File size | 108,363 bytes |
| Rows | 1,200 |
| Columns | 13 |
| Extra columns | None |
| Column names | record_id, production_date, plant, production_line, machine_id, shift, product_code, produced_quantity, good_quantity, scrap_quantity, downtime_minutes, planned_minutes, cycle_time_seconds |

Dtypes produced by a normal `pandas.read_csv` call:

| Column | Pandas dtype | Why this dtype appeared |
| --- | --- | --- |
| record_id | object | Text identifiers, plus one missing value. |
| production_date | object | Dates stored as text, including one impossible date. |
| plant | object | Text plant name. |
| production_line | object | Text line names. |
| machine_id | object | Text machine IDs, plus one missing value. |
| shift | object | Text shift names. |
| product_code | object | Text product codes, plus one missing value. |
| produced_quantity | object | Almost all numbers, but one cell contains `unknown`. |
| good_quantity | int64 | Whole numbers only, including one negative value. |
| scrap_quantity | int64 | Whole numbers only, including one negative value. |
| downtime_minutes | int64 | Whole numbers only, including one negative value. |
| planned_minutes | int64 | Whole numbers only. Every parsed value is 480. |
| cycle_time_seconds | object | Decimal numbers mixed with one text value (`fast`). |

## Allowed business values found

| Column | Values present in the file | Contract values | Notes |
| --- | --- | --- | --- |
| plant | Plant-01 | Any non-blank plant | All 1,200 rows are Plant-01. None are blank. |
| production_line | Line-A (600), Line-B (600) | Line-A, Line-B | No unexpected lines. |
| machine_id | MC-101 (300), MC-102 (298), MC-201 (300), MC-202 (300), MC-999 (1), missing (1) | MC-101, MC-102, MC-201, MC-202 | One unknown machine and one blank machine. |
| shift | Day (400), Night (400), Evening (399), Weekend (1) | Day, Evening, Night | One `Weekend` value is outside the contract. |
| product_code | PRD-A100 (300), PRD-B200 (300), PRD-C300 (300), PRD-D400 (299), missing (1) | PRD-A100, PRD-B200, PRD-C300, PRD-D400 | One blank product code. |

Parseable production dates run from **2026-01-01** through **2026-04-10**.

## Missing and duplicate values

Pandas missing-value counts (`NaN` after a normal read):

| Column | Missing count | Blank strings after stripping | Notes |
| --- | --- | --- | --- |
| record_id | 1 | 1 | One row has no record ID. Pandas reads the empty cell as missing. |
| production_date | 0 | 0 | One date is present but not parseable; see type problems. |
| plant | 0 | 0 | |
| production_line | 0 | 0 | |
| machine_id | 1 | 1 | |
| shift | 0 | 0 | |
| product_code | 1 | 1 | |
| produced_quantity | 0 | 0 | |
| good_quantity | 0 | 0 | |
| scrap_quantity | 0 | 0 | |
| downtime_minutes | 0 | 0 | |
| planned_minutes | 0 | 0 | |
| cycle_time_seconds | 0 | 0 | |

No extra whitespace-only strings were found. Empty cells are stored as pandas missing values.

Duplicate identifiers:

| Check | Result |
| --- | --- |
| Unique `record_id` values, including the missing ID | 1,199 |
| Distinct non-missing identifiers | 1,198 |
| Identifier that appears twice | PR-2026-000072 |
| Rows sharing that identifier | 2 |
| Extra duplicate occurrences | 1 |

## Type problems

| Column | Non-numeric or unparseable count | Sample invalid value |
| --- | --- | --- |
| production_date | 1 date that cannot be parsed | 2026-02-30 |
| produced_quantity | 1 | unknown |
| good_quantity | 0 | |
| scrap_quantity | 0 | |
| downtime_minutes | 0 | |
| planned_minutes | 0 | |
| cycle_time_seconds | 1 | fast |

Earliest parseable date: 2026-01-01. Latest parseable date: 2026-04-10.

## Range problems

Negative values are forbidden in every numeric business column. Planned minutes and cycle time must also be greater than zero.

| Column | Negative values | Zero values | Comment |
| --- | --- | --- | --- |
| produced_quantity | 1 | 1 | Zero is allowed. The negative value is `-25`. |
| good_quantity | 1 | 1 | Zero is allowed. The negative value is `-10`. |
| scrap_quantity | 1 | 2 | Zero is allowed. The negative value is `-3`. |
| downtime_minutes | 1 | 13 | Zero is allowed and appears on valid no-stoppage rows. The negative value is `-15`. |
| planned_minutes | 0 | 0 | All 1,200 values are 480, so this column currently has no range failures. |
| cycle_time_seconds | 0 | 1 | Zero is **not** allowed. There is also one non-numeric `fast` value counted under type problems. |

Valid boundary examples that should stay in the file include produced quantity `0`, good quantity `0`, scrap quantity `0`, and downtime `0`.

## Cross-column problems

Counts only include rows where the compared fields could be read as numbers.

| Check | Count | Example |
| --- | --- | --- |
| good_quantity + scrap_quantity exceeds produced_quantity | 2 | One row has produced quantity `-25` against good 3529 and scrap 97. Another has produced 2688, good 2688, and scrap 10. |
| downtime_minutes exceeds planned_minutes | 1 | downtime 600 against planned 480 |

## Conclusion

The extract is the right shape for Stage 1: 1,200 synthetic rows and the expected 13 columns. It also contains planted defects, including a blank record ID, a duplicated ID, an impossible date, an unknown machine, a Weekend shift, a blank product code, text in numeric fields, negative quantities, a zero cycle time, an impossible quantity split, and downtime longer than the plan.

Those defects must be left in `data/production_data.csv`. Later stages should detect them, not repair the source file.
