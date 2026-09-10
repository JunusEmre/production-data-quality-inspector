# Production Data Dictionary

This dictionary explains the manufacturing fields in `data/production_data.csv`. It is written for production managers as well as developers. The file is synthetic teaching data, not a live factory extract.

| Column | Business meaning | Expected type | Example | Required | Main rule |
| --- | --- | --- | --- | --- | --- |
| record_id | Unique tracking number for one production row so a shift result can be found again later. | Text | PR-2026-000001 | Yes | RECORD_ID_PRESENT, UNIQUE_RECORD_ID |
| production_date | Calendar date when the work was produced. | Date | 2026-01-01 | Yes | VALID_PRODUCTION_DATE |
| plant | Factory that produced the work. | Text | Plant-01 | Yes | PLANT_PRESENT |
| production_line | Physical line inside the plant. Only Line-A and Line-B are in the current layout. | Text | Line-A | Yes | VALID_PRODUCTION_LINE |
| machine_id | Machine that ran the product. Allowed machines are MC-101, MC-102, MC-201, and MC-202. | Text | MC-101 | Yes | VALID_MACHINE_ID |
| shift | Working shift that produced the row. Allowed values are Day, Evening, and Night. | Text | Day | Yes | VALID_SHIFT |
| product_code | Product made during the run. Allowed codes are PRD-A100, PRD-B200, PRD-C300, and PRD-D400. | Text | PRD-A100 | Yes | VALID_PRODUCT_CODE |
| produced_quantity | Total units made during the planned time, including good units and scrap. | Number (zero or more) | 5260 | Yes | PRODUCED_QUANTITY_RANGE |
| good_quantity | Units that passed quality and can be shipped or used. | Number (zero or more) | 5168 | Yes | GOOD_QUANTITY_RANGE |
| scrap_quantity | Units lost to defects or process waste. | Number (zero or more) | 92 | Yes | SCRAP_QUANTITY_RANGE |
| downtime_minutes | Minutes the machine or line was stopped during the planned run. Zero is allowed and means no stoppage. | Number (zero or more) | 0 | Yes | DOWNTIME_MINUTES_RANGE |
| planned_minutes | Minutes the run was supposed to operate. This value must be greater than zero. | Number (greater than zero) | 480 | Yes | PLANNED_MINUTES_RANGE |
| cycle_time_seconds | Average seconds needed to make one unit. This value must be greater than zero. | Number (greater than zero) | 4.86 | Yes | CYCLE_TIME_RANGE |

Two extra checks look across columns rather than at a single field:

- **QUANTITY_BALANCE:** good quantity plus scrap quantity must not exceed produced quantity.
- **DOWNTIME_WITHIN_PLAN:** downtime minutes must not exceed planned minutes.

The extract as a whole must also contain all 13 required columns, report unexpected extra columns, and include at least one production row.
