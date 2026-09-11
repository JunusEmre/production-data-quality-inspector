"""English Streamlit dashboard for production data quality inspection."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from production_quality.data import load_production_data
from production_quality.exceptions import ProductionQualityError
from production_quality.manual_validation import validate_with_pandas
from production_quality.models import ValidationResult
from production_quality.quality import QualitySummary, calculate_quality_summary
from production_quality.reporting import (
    build_affected_records,
    build_issue_report,
    build_quality_summary_frame,
    build_rule_summary,
    dataframe_to_csv_bytes,
)
from production_quality.rules import VALIDATION_RULES
from production_quality.validation import validate_with_pandera

LOGGER = logging.getLogger(__name__)
DEMO_DATA_PATH = Path(__file__).resolve().parent / "data" / "production_data.csv"
SOURCE_UPLOAD = "Upload a CSV"
SOURCE_DEMO = "Use demonstration dataset"
SCORE_EXPLANATION = (
    "The score shows how many rows have no Error findings. "
    "The file is still not approved while any Error remains."
)


@dataclass
class InspectionBundle:
    """Stored inspection outputs for one selected file."""

    complete: ValidationResult
    direct: ValidationResult
    manual: ValidationResult
    summary: QualitySummary
    issues: pd.DataFrame
    affected: pd.DataFrame
    rules: pd.DataFrame
    quality_frame: pd.DataFrame


def inspect_dataset(data: pd.DataFrame) -> InspectionBundle:
    """Run production inspection and educational comparison on one extract."""

    complete = validate_with_pandera(data, lazy=True)
    direct = validate_with_pandera(data, lazy=False)
    manual = validate_with_pandas(data)
    summary = calculate_quality_summary(data, complete)
    return InspectionBundle(
        complete=complete,
        direct=direct,
        manual=manual,
        summary=summary,
        issues=build_issue_report(data, complete),
        affected=build_affected_records(data, complete),
        rules=build_rule_summary(complete),
        quality_frame=build_quality_summary_frame(summary),
    )


def main() -> None:
    """Render the production data quality dashboard."""

    st.set_page_config(
        page_title="Production Data Quality Inspector",
        page_icon="🏭",
        layout="wide",
    )
    _inject_layout_css()
    st.title("Production Data Quality Inspector")
    st.caption(
        "Inspect a manufacturing production extract without changing the source values."
    )
    _render_workflow()
    frame, source_name = _load_selected_source()
    if frame is None:
        return
    _render_preview(frame, source_name)
    if st.button("Run quality inspection", type="primary", key="run_inspection"):
        _run_inspection(frame)
    _render_user_error()
    inspection = st.session_state.get("inspection")
    if inspection is None:
        return
    _render_result_header(inspection.summary)
    _render_result_tabs(inspection)


def _inject_layout_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.6rem; padding-bottom: 3rem; }
        h1, h2, h3 { letter-spacing: 0.01em; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_workflow() -> None:
    st.caption(
        "Choose source → Preview → Inspect → Review problems → Download reports"
    )


def _load_selected_source() -> tuple[pd.DataFrame | None, str | None]:
    source = st.radio(
        "Data source",
        (SOURCE_DEMO, SOURCE_UPLOAD),
        key="data_source",
        horizontal=True,
    )
    try:
        if source == SOURCE_DEMO:
            return _load_demo_source()
        return _load_upload_source()
    except ProductionQualityError as exc:
        _set_file_error(str(exc))
        return None, None
    except Exception:
        LOGGER.exception("Could not load the selected production file")
        _set_file_error(
            "The file could not be read as a production CSV. Check the file and try again."
        )
        return None, None


def _load_demo_source() -> tuple[pd.DataFrame, str]:
    file_bytes = DEMO_DATA_PATH.read_bytes()
    signature = _sha256(file_bytes)
    _remember_source(signature, "production_data.csv")
    st.info(
        "This demonstration file is synthetic. It contains no confidential production "
        "information and intentionally includes quality problems."
    )
    frame = load_production_data(DEMO_DATA_PATH)
    return frame, "production_data.csv"


def _load_upload_source() -> tuple[pd.DataFrame | None, str | None]:
    uploaded = st.file_uploader("Upload a CSV file", type=["csv"], key="csv_upload")
    if uploaded is None:
        st.session_state.pop("inspection", None)
        return None, None
    file_bytes = uploaded.getvalue()
    signature = _sha256(file_bytes)
    _remember_source(signature, uploaded.name)
    frame = load_production_data(BytesIO(file_bytes))
    return frame, uploaded.name


def _remember_source(signature: str, source_name: str) -> None:
    if st.session_state.get("source_signature") != signature:
        st.session_state.pop("inspection", None)
        st.session_state.pop("user_error", None)
        st.session_state["source_signature"] = signature
    st.session_state["source_name"] = source_name


def _set_file_error(message: str) -> None:
    st.session_state.pop("inspection", None)
    st.session_state["user_error"] = message
    st.error(message)


def _run_inspection(frame: pd.DataFrame) -> None:
    try:
        st.session_state["inspection"] = inspect_dataset(frame)
        st.session_state.pop("user_error", None)
    except ProductionQualityError as exc:
        st.session_state.pop("inspection", None)
        st.session_state["user_error"] = str(exc)
    except Exception:
        LOGGER.exception("Unexpected error during quality inspection")
        st.session_state.pop("inspection", None)
        st.session_state["user_error"] = (
            "The inspection could not be completed. Check that the file is a "
            "valid production CSV and try again."
        )


def _render_user_error() -> None:
    message = st.session_state.get("user_error")
    if message:
        st.error(message)


def _render_preview(frame: pd.DataFrame, source_name: str) -> None:
    st.subheader("Preview")
    preview_rows = min(100, len(frame))
    metric_cols = st.columns(3)
    metric_cols[0].metric("Source", source_name)
    metric_cols[1].metric("Rows", f"{len(frame):,}")
    metric_cols[2].metric("Columns", f"{frame.shape[1]}")
    st.caption(
        f"Showing the first {preview_rows} rows. Previewing does not alter the data."
    )
    st.dataframe(frame.head(preview_rows), width="stretch")


def _render_result_header(summary: QualitySummary) -> None:
    st.subheader("Inspection result")
    _status_banner(summary.status)
    st.info(SCORE_EXPLANATION)
    cards = st.columns(6)
    cards[0].metric("Row-cleanliness score", _score_label(summary))
    cards[1].metric("Total rows", f"{summary.total_rows:,}")
    cards[2].metric("Clean rows", _optional_count(summary.clean_rows))
    cards[3].metric("Affected rows", _optional_count(summary.affected_rows))
    cards[4].metric("Error findings", f"{summary.error_count:,}")
    cards[5].metric("Warning findings", f"{summary.warning_count:,}")


def _status_banner(status: str) -> None:
    if status == "Passed":
        st.success(f"Status: {status}")
    elif status == "Passed with warnings":
        st.warning(f"Status: {status}")
    else:
        st.error(f"Status: {status}")


def _score_label(summary: QualitySummary) -> str:
    if summary.score is None:
        return "Not scorable"
    return f"{summary.score:.2f}%"


def _optional_count(value: int | None) -> str:
    if value is None:
        return "Not scorable"
    return f"{value:,}"


def _render_result_tabs(inspection: InspectionBundle) -> None:
    overview, issues, affected, rulebook, comparison, downloads = st.tabs(
        [
            "Overview",
            "Issues",
            "Affected records",
            "Rulebook",
            "Validation comparison",
            "Downloads",
        ]
    )
    with overview:
        _render_overview(inspection)
    with issues:
        _render_issues(inspection.issues)
    with affected:
        _render_affected(inspection.affected)
    with rulebook:
        _render_rulebook(inspection.rules)
    with comparison:
        _render_comparison(inspection)
    with downloads:
        _render_downloads(inspection)


def _render_overview(inspection: InspectionBundle) -> None:
    summary = inspection.summary
    st.markdown(f"**Status:** {summary.status}")
    failed = inspection.rules[inspection.rules["result"] == "Error"].copy()
    if failed.empty:
        st.success("No Error findings were detected.")
        return
    failed = failed.sort_values(
        by=["finding_count", "title"],
        ascending=[False, True],
        kind="mergesort",
    )
    st.markdown("**Error findings by rule**")
    chart = failed.loc[:, ["title", "finding_count"]].rename(
        columns={"title": "Rule", "finding_count": "Error findings"}
    )
    st.bar_chart(
        chart,
        x="Rule",
        y="Error findings",
        horizontal=True,
        x_label="Error findings",
        y_label="",
        sort=False,
        color="primary",
        height=max(360, 44 * len(chart) + 48),
        width="stretch",
    )
    frequent = failed.loc[:, ["title", "finding_count", "affected_row_count"]].head(5)
    frequent = frequent.rename(
        columns={
            "title": "Problem",
            "finding_count": "Findings",
            "affected_row_count": "Affected rows",
        }
    )
    st.markdown("**Most frequent problems**")
    st.dataframe(frequent, hide_index=True, width="stretch")


def _render_issues(issues: pd.DataFrame) -> None:
    if issues.empty:
        st.success("No findings were reported.")
        return
    severities = sorted(issues["severity"].dropna().astype(str).unique().tolist())
    rules = issues["rule_id"].dropna().astype(str).tolist()
    rules = list(dict.fromkeys(rules))
    columns = sorted(
        value for value in issues["column"].dropna().astype(str).unique().tolist()
    )
    selected_severity = st.multiselect(
        "Severity",
        options=severities,
        default=severities,
        key="filter_severity",
        help="Leave every option selected to display all values.",
    )
    selected_rules = st.multiselect(
        "Rule",
        options=rules,
        default=rules,
        key="filter_rule",
        help="Leave every option selected to display all values.",
    )
    selected_columns = st.multiselect(
        "Field",
        options=columns,
        default=columns,
        key="filter_column",
        help="Leave every option selected to display all values.",
    )
    visible = issues.copy()
    if selected_severity:
        visible = visible[visible["severity"].isin(selected_severity)]
    else:
        visible = visible.iloc[0:0]
    if selected_rules:
        visible = visible[visible["rule_id"].isin(selected_rules)]
    else:
        visible = visible.iloc[0:0]
    if columns:
        if selected_columns:
            visible = visible[
                visible["column"].isin(selected_columns) | visible["column"].isna()
            ]
        else:
            visible = visible[visible["column"].isna()]
    showing_all = (
        set(selected_severity) == set(severities)
        and set(selected_rules) == set(rules)
        and (not columns or set(selected_columns) == set(columns))
    )
    if showing_all:
        st.caption(f"All {len(issues):,} findings are currently displayed.")
    else:
        st.caption(f"Showing {len(visible):,} of {len(issues):,} findings.")
    display = visible.rename(
        columns={
            "severity": "Severity",
            "rule_id": "Rule ID",
            "rule_title": "Rule",
            "message": "Explanation",
            "row_index": "Source row",
            "record_id": "Record ID",
            "column": "Field",
            "failure_value": "Original value",
        }
    )
    st.dataframe(display, hide_index=True, width="stretch")


def _render_affected(affected: pd.DataFrame) -> None:
    st.caption(
        "These are original source values. The application has not repaired them."
    )
    if affected.empty:
        st.success("No source rows are connected to Error findings.")
        return
    display = affected.rename(
        columns={
            "source_row": "Source row",
            "error_count": "Error count",
            "warning_count": "Warning count",
            "failed_rules": "Failed rules",
        }
    )
    st.dataframe(display, hide_index=True, width="stretch")


def _render_rulebook(rules: pd.DataFrame) -> None:
    rows = []
    for rule in VALIDATION_RULES:
        current = rules.loc[rules["rule_id"] == rule.rule_id].iloc[0]
        rows.append(
            {
                "Rule ID": rule.rule_id,
                "Rule": rule.title,
                "Description": rule.description,
                "Severity": rule.severity,
                "Fields": ", ".join(rule.columns) if rule.columns else "Entire file",
                "Result": current["result"],
                "Findings": int(current["finding_count"]),
                "Affected rows": int(current["affected_row_count"]),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_comparison(inspection: InspectionBundle) -> None:
    st.markdown(
        """
Direct Pandera stops after the first serious failure. Complete/lazy Pandera
checks the batch more fully and collects independent problems. Manual Pandas
can produce the same business result but requires more handwritten checking code.
Pandera is the application’s production engine. The manual validator exists only
for learning and comparison.
        """
    )
    comparison = pd.DataFrame(
        [
            _comparison_row("Pandera", "Direct", inspection.direct),
            _comparison_row("Pandera", "Complete", inspection.complete),
            _comparison_row("Pandas", "Manual", inspection.manual),
        ]
    )
    st.dataframe(comparison, hide_index=True, width="stretch")
    with st.expander("Detected rule IDs"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Validator": "Pandera — Direct",
                        "Rule IDs": _rule_id_list(inspection.direct),
                    },
                    {
                        "Validator": "Pandera — Complete",
                        "Rule IDs": _rule_id_list(inspection.complete),
                    },
                    {
                        "Validator": "Pandas — Manual",
                        "Rule IDs": _rule_id_list(inspection.manual),
                    },
                ]
            ),
            hide_index=True,
            width="stretch",
        )


def _comparison_row(validator: str, mode: str, result: ValidationResult) -> dict[str, object]:
    categories = {issue.rule_id for issue in result.issues}
    return {
        "Validator": validator,
        "Mode": mode,
        "Valid": "Yes" if result.is_valid else "No",
        "Error findings": result.error_count,
        "Warning findings": result.warning_count,
        "Affected rows": result.affected_row_count,
        "Detected rule categories": len(categories),
    }


def _rule_id_list(result: ValidationResult) -> str:
    ids = []
    for issue in result.issues:
        if issue.rule_id not in ids:
            ids.append(issue.rule_id)
    return ", ".join(ids) if ids else "None"


def _render_downloads(inspection: InspectionBundle) -> None:
    st.caption("Downloads are built in memory. Source data is not repaired.")
    top_left, top_right = st.columns(2)
    bottom_left, bottom_right = st.columns(2)
    with top_left:
        _download_button(
            "quality_summary.csv",
            inspection.quality_frame,
            "Download quality summary",
        )
    with top_right:
        if inspection.issues.empty:
            st.info("There are no issue findings to download for this extract.")
        else:
            _download_button(
                "quality_issues.csv",
                inspection.issues,
                "Download quality issues",
            )
    with bottom_left:
        if inspection.affected.empty:
            st.info("There are no affected records to download for this extract.")
        else:
            _download_button(
                "affected_records.csv",
                inspection.affected,
                "Download affected records",
            )
    with bottom_right:
        _download_button(
            "validation_rule_summary.csv",
            inspection.rules,
            "Download rule summary",
        )


def _download_button(filename: str, frame: pd.DataFrame, label: str) -> None:
    st.download_button(
        label=label,
        data=dataframe_to_csv_bytes(frame),
        file_name=filename,
        mime="text/csv",
        key=f"download_{filename}",
    )


def _sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


if __name__ == "__main__":
    main()
