# Row-cleanliness score

The dashboard reports a **row-cleanliness score**. This is not a grade for the
factory and it is not a pass mark. It only answers one operational question:

> What share of production rows has no Error findings?

## Why it is called a row-cleanliness score

In manufacturing, yield measures how many units come through a process without
a defect. This score uses the same idea on data. Each production row is one
unit. A row is “clean” when no Error rule failed on it. Warnings, such as an
unexpected extra column, do not change that count.

The inspection decision stays separate. If any Error exists, the extract is
not approved, even when the score is high.

## Exact formula

When the file is scorable:

```text
clean_rows = total_rows - affected_error_rows
score = round((clean_rows / total_rows) * 100, 2)
```

Each affected row is counted once, even if several Error rules failed on it.

## Why each row counts once

A machine row with a Weekend shift and a negative quantity is still one
unreliable record. Counting it twice would make the score look worse than the
number of records that need attention.

## Why Warnings do not reduce the score

A Warning means “review this.” An extra column does not, by itself, make a
production row unusable. The score therefore ignores Warnings. The status
still changes to **Passed with warnings** so the extra field is not hidden.

## Why any Error still makes the file invalid

Example from the demonstration extract:

- Total rows: 1,200
- Rows affected by Errors: 17
- Clean rows: 1,183
- Row-cleanliness score: 98.58%
- Overall status: **Issues found**

98.58% sounds high, but 17 rows still contain unreliable values. Those rows
can distort output, scrap, or downtime. The file is therefore not approved.

The score never determines the status. Error findings do.

## Why missing columns make the file Not scorable

If a required column is missing, later row checks cannot be trusted. The
application cannot fairly say how many rows are clean because part of the
contract is absent. The status is **Not scorable** and the score is left
blank. It is not shown as 0%.

An empty extract is also Not scorable: there are no production rows to score.

## Demonstration calculation

| Item | Value |
| --- | --- |
| Total rows | 1,200 |
| Affected rows | 17 |
| Clean rows | 1,183 |
| Score | 98.58% |
| Error findings | 18 |
| Warning findings | 0 |
| Status | Issues found |

18 Error findings can sit on 17 rows because one row can break more than one
rule. The score uses the 17 rows, not the 18 findings.

## Limitations

- The score does not measure business impact. One impossible quantity can
  matter more than a blank product code, but this project does not guess that.
- The score does not become 100% when Warnings exist; it can stay 100.00%
  while the status is **Passed with warnings**.
- The score is not a traffic-light. This project does not use subjective
  green, amber, or red thresholds.
- The score is not a quality KPI for the plant. It only describes the extract.

## Why there is no weighting or threshold

Subjective weights would hide a policy choice inside a number. A 90% cut-off
would also make a high score look like approval. The approved rule is
simpler: report the share of clean rows, and keep the validation decision
based on Errors.
