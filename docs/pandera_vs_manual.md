# Pandera versus manual pandas validation

This note explains the two Stage 2 validators in manufacturing language. The
production engine is Pandera. The pandas version exists so the assignment can
show how much extra code is needed without a schema library.

## What Pandera is

Pandera is a Python library that turns a DataFrame contract into an executable
schema. Instead of writing a long chain of `if` checks, you declare the
expected columns, allowed values, and numeric limits. Pandera then inspects a
pandas DataFrame against that contract.

## What a DataFrame schema means

A schema is a specification for a table:

- which columns must exist
- which values are allowed
- which numbers must be zero or more, or greater than zero
- which pairs of columns must stay mathematically consistent

In this project the schema lives in `production_quality/schema.py` and is built
from `PRODUCTION_DATA_CONFIG`. Allowed machines, shifts, products, and lines
are not copied into a second list.

## Schema as a production specification

The 19 business rules in `VALIDATION_RULES` are the human-readable contract.
The Pandera schema is the same contract in executable form. Production
managers can read the rule catalog; the application uses the schema to inspect
each incoming extract.

## Direct validation versus lazy validation

Pandera can run in two modes:

- **Direct** (`lazy=False`): stop at the first schema failure. This is useful
  when a file is so badly structured that later checks would be noise.
- **Lazy** (`lazy=True`): keep going and collect independent failures. This is
  the default for a complete incoming-batch inspection.

Both modes still report extra columns as **Warning** before schema checks run.
An extra column does not, by itself, make the extract invalid.

```python
from production_quality import validate_with_pandera

direct = validate_with_pandera(frame, lazy=False)
batch = validate_with_pandera(frame, lazy=True)
```

## Why lazy validation is useful for a complete incoming-batch inspection

A production extract can have several unrelated problems in the same file: a
Weekend shift, an unknown machine, text in a quantity field, and an impossible
date. Direct validation would show only the first of those. Lazy validation
gives the plant a full punch list so one repair pass can address every
independent defect.

## How failures become ValidationIssue records

Pandera exceptions are not shown to users. The validation service maps each
finding onto the existing rule catalog and stores a `ValidationIssue`:

- `rule_id` such as `VALID_SHIFT` or `QUANTITY_BALANCE`
- `severity` from the catalog (`Error` or `Warning`)
- a short manager-facing `message` built from the rule title
- `column`, `row_index`, and the original `failure_value` where they exist

`ValidationResult` then answers operational questions: is the file usable
(`is_valid`), how many Errors and Warnings were found, and how many source
rows are affected.

## Why the project keeps the source data unchanged

The demonstration CSV is designed to contain bad values. If the application
quietly replaced `unknown` with 0, or `2026-02-30` with a missing date, the
report would hide the original defect. Validation therefore works on copies.
The caller's DataFrame is never mutated, and `failure_value` keeps the original
cell when it can.

Narrow preparation is allowed on a copy only: whitespace-only cells are treated
as blank so presence checks can run. Unparseable text is **not** converted into
an accepted missing number.

When a file has no Error issues, the service may coerce valid dates and
numeric columns on the successful copy so later code receives typed data.

## What the manual pandas version needs to do

`validate_with_pandas` re-implements the same 19 rules with ordinary pandas:
column membership, `isin`, `duplicated`, `to_numeric`, and boolean masks. It
must handle missing columns, blank cells, mixed text and numbers, and
cross-column comparisons without crashing. That is a long function, and every
new rule adds more branches. It does not import Pandera and will not power the
dashboard.

## Comparison

| Topic | Pandera | Manual pandas |
| --- | --- | --- |
| How rules are expressed | A schema built from the shared config | Handwritten checks for each rule |
| Extra columns | Detected in the validation service as Warning | Detected with a column-name loop as Warning |
| Direct vs lazy | Native `lazy=False` / `lazy=True` | Always walks every implemented check |
| Cross-column rules | Named DataFrame checks | Extra pandas masks |
| Code volume | Compact once the schema exists | Grows with every new rule |
| Teaching value | Shows declarative validation | Shows the work a schema avoids |
| Production use in this project | Yes, this is the engine | No, comparison only |

## Advantages and disadvantages of Pandera

**Advantages**

- The contract is declared once and reused.
- Lazy mode collects independent failures for a whole batch.
- Check names map cleanly onto the existing rule IDs.
- Direct mode can fail fast when that is wanted.

**Disadvantages**

- Mixed text and numbers need careful checks so coercion does not hide defects.
- Failure objects are library-specific and must be translated into
  `ValidationIssue` records.
- Teams still have to design around extra columns, because this project treats
  them as warnings rather than fatal schema errors.

## Advantages and disadvantages of manual pandas checks

**Advantages**

- Every step is ordinary pandas, which many analysts already know.
- It is easy to compare outcomes with the schema for teaching.
- There is no extra library behaviour to learn for the comparison itself.

**Disadvantages**

- The same 19 rules become a long, easy-to-drift checklist.
- There is no built-in direct/lazy split.
- It would be a second production engine if the dashboard called it, which this
  project deliberately avoids.

## Why Pandera is the production engine

The assignment is about declarative validation. Pandera keeps the manufacturing
contract in one schema, supports a full incoming-batch scan, and is the API the
later Streamlit dashboard should call: `validate_with_pandera` and
`validate_file_with_pandera`.

## Why manual validation remains a learning comparison

The pandas validator proves that both approaches can agree on valid versus
invalid, Warning versus Error, rule IDs, and affected rows. It is not a backup
engine. Keeping it separate prevents the dashboard from accumulating two
sources of truth.
