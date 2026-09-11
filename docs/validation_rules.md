# Production Validation Rules

These 19 rules are the agreed data-quality contract for manufacturing production extracts. Stage 2 implements them in two places:

- **Pandera** (`validate_with_pandera`) is the production engine.
- **Manual pandas** (`validate_with_pandas`) is an educational comparison only.

Both read rule IDs, titles, descriptions, and severity from `VALIDATION_RULES`. Extra columns are a **Warning** and do not by themselves make the extract invalid. The other 18 rules are **Errors**.

| Rule ID | Business rule | Why it matters | Severity | Scope | Columns involved |
| --- | --- | --- | --- | --- | --- |
| REQUIRED_COLUMNS | All 13 required columns must exist. | A missing field such as scrap or downtime leaves the report incomplete. | Error | File / columns | All 13 required columns |
| UNEXPECTED_COLUMNS | Unexpected extra columns should be reported. | Extra fields often mean the extract layout changed and needs a review before those values are trusted. | Warning | File / columns | Unexpected extra columns |
| NONEMPTY_DATASET | The file must contain at least one production row. | Headers without rows cannot describe output, scrap, or downtime. | Error | File | Entire file |
| RECORD_ID_PRESENT | record_id must not be blank. | Without an ID, a suspect row cannot be traced back to a shift or machine. | Error | One column | record_id |
| UNIQUE_RECORD_ID | record_id must be unique. | Duplicate IDs can hide a repeated export or two different events sharing one identifier. | Error | One column | record_id |
| VALID_PRODUCTION_DATE | production_date must contain a valid date. | Impossible dates, such as 30 February, cannot be placed on a production calendar. | Error | One column | production_date |
| PLANT_PRESENT | plant must not be blank. | Output and downtime need a factory owner. | Error | One column | plant |
| VALID_PRODUCTION_LINE | production_line must be Line-A or Line-B. | Any other line is outside the current plant layout. | Error | One column | production_line |
| VALID_MACHINE_ID | machine_id must be one of MC-101, MC-102, MC-201, or MC-202. | Unknown machines cannot be tied to maintenance or scrap investigation. | Error | One column | machine_id |
| VALID_SHIFT | shift must be Day, Evening, or Night. | Other labels break the three-shift reporting pattern. | Error | One column | shift |
| VALID_PRODUCT_CODE | product_code must be one of PRD-A100, PRD-B200, PRD-C300, or PRD-D400. | Unknown or missing codes prevent finished output from being assigned to a known product. | Error | One column | product_code |
| PRODUCED_QUANTITY_RANGE | produced_quantity must be numeric and greater than or equal to zero. | Negative or text output cannot be added into production totals. Zero is allowed and can mean no units were made. | Error | One column | produced_quantity |
| GOOD_QUANTITY_RANGE | good_quantity must be numeric and greater than or equal to zero. | Negative good quantity corrupts yield. | Error | One column | good_quantity |
| SCRAP_QUANTITY_RANGE | scrap_quantity must be numeric and greater than or equal to zero. | Negative scrap hides loss. | Error | One column | scrap_quantity |
| DOWNTIME_MINUTES_RANGE | downtime_minutes must be numeric and greater than or equal to zero. | Negative downtime cannot be used in availability reviews. Zero is allowed and means no stoppage. | Error | One column | downtime_minutes |
| PLANNED_MINUTES_RANGE | planned_minutes must be numeric and greater than zero. | A zero or negative plan makes it impossible to judge the run against intended time. | Error | One column | planned_minutes |
| CYCLE_TIME_RANGE | cycle_time_seconds must be numeric and greater than zero. | Zero, negative, or text values such as "fast" are not usable cycle times. | Error | One column | cycle_time_seconds |
| QUANTITY_BALANCE | good_quantity plus scrap_quantity must not exceed produced_quantity. | If good and scrap add up to more than total output, the quantity split is impossible. | Error | Several columns | produced_quantity, good_quantity, scrap_quantity |
| DOWNTIME_WITHIN_PLAN | downtime_minutes must not exceed planned_minutes. | A machine cannot be down longer than the minutes planned for that run. | Error | Several columns | downtime_minutes, planned_minutes |

Severity guide:

- **Error** means the row or file is structurally or mathematically unreliable.
- **Warning** means the file should be reviewed, but the extra information does not by itself make the required production fields unusable.

Column-scope guide:

- **File / columns** rules inspect the table shape (missing columns, extra columns, no rows).
- **One column** rules inspect a single field on each row.
- **Several columns** rules compare fields on the same row. They only run the comparison when the involved values are numeric, so a text quantity is reported by its range rule rather than as a misleading balance failure.
