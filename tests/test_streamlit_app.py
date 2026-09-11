"""Tests for the Streamlit dashboard shell."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from streamlit_app import CHART_CAPTION

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "streamlit_app.py"
WORKFLOW = "Choose source → Preview → Inspect → Review problems → Download reports"
SCORE_TEXT = "The score shows how many rows have no Error findings."
TOP_TEN_LABELS = [
    "Duplicate record IDs",
    "Invalid machine IDs",
    "Invalid produced quantities",
    "Invalid cycle times",
    "Quantity imbalance",
    "Missing record IDs",
    "Invalid production dates",
    "Invalid shifts",
    "Invalid product codes",
    "Invalid good quantities",
]
TOP_TEN_CHART_LABELS = [
    "Duplicate IDs",
    "Machine IDs",
    "Produced quantity",
    "Cycle time",
    "Quantity balance",
    "Missing IDs",
    "Dates",
    "Shifts",
    "Product codes",
    "Good quantity",
]
TOP_TEN_FINDINGS = [2, 2, 2, 2, 2, 1, 1, 1, 1, 1]


def _start_app(timeout: int = 15) -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=timeout).run()


def _visible_text(app: AppTest) -> str:
    return " ".join(
        [
            *(item.value for item in app.title),
            *(item.value for item in app.markdown),
            *(item.value for item in app.caption),
            *(str(item.value) for item in app.info),
            *(str(item.value) for item in app.error),
            *(str(item.value) for item in app.success),
            *(str(item.value) for item in app.warning),
            *(f"{item.label} {item.value}" for item in app.metric),
            *(item.label for item in app.button),
            *(item.label for item in app.download_button),
            *(item.label for item in app.multiselect),
        ]
    )


def test_app_starts_without_an_exception() -> None:
    app = _start_app()
    assert not app.exception


def test_compact_workflow_wording_is_visible() -> None:
    app = _start_app()
    assert any("Production Data Quality Inspector" in title.value for title in app.title)
    text = _visible_text(app)
    assert WORKFLOW in text
    assert "1. Choose a data source" not in text


def test_demonstration_dataset_is_the_default() -> None:
    app = _start_app()
    radio = app.radio(key="data_source")
    assert "Use demonstration dataset" in [str(option) for option in radio.options]
    assert "Upload a CSV" in [str(option) for option in radio.options]
    assert radio.value == "Use demonstration dataset"
    assert any(widget.label == "Run quality inspection" for widget in app.button)


def test_importing_streamlit_app_does_not_start_or_write_files(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path\n"
                "import streamlit_app\n"
                "assert streamlit_app.SOURCE_DEMO\n"
                "print('imported')\n"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert list(tmp_path.iterdir()) == []


def test_demonstration_inspection_shows_expected_result() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=60).run()
    app.radio(key="data_source").set_value("Use demonstration dataset").run()
    app.button(key="run_inspection").click().run(timeout=60)
    assert not app.exception
    body = _visible_text(app)
    assert "Issues found" in body
    assert "98.58%" in body
    assert "1,200" in body or "1200" in body
    assert "1,183" in body or "1183" in body
    assert "17" in body
    assert "18" in body
    assert body.count(SCORE_TEXT) == 1
    assert "Top 10 Error findings by rule" in body
    assert CHART_CAPTION in body
    tab_labels = [tab.label for tab in getattr(app, "tabs", [])] or [
        tab.label for tab in getattr(app, "tab", [])
    ]
    combined = " ".join(tab_labels) if tab_labels else body
    for name in (
        "Overview",
        "Issues",
        "Affected records",
        "Rulebook",
        "Validation comparison",
        "Downloads",
    ):
        assert name in combined or name in body


def test_human_friendly_labels_and_downloads_after_inspection() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=60).run()
    app.button(key="run_inspection").click().run(timeout=60)
    assert not app.exception
    frames = [item.value for item in app.dataframe]
    frequent = next(
        frame
        for frame in frames
        if list(frame.columns) == ["Problem", "Findings", "Affected rows"]
    )
    assert list(frequent["Problem"]) == TOP_TEN_LABELS
    assert list(frequent["Findings"]) == TOP_TEN_FINDINGS
    assert len(frequent) == 10
    assert "Chart label" not in frequent.columns
    assert "finding_count" not in frequent.columns
    assert "title" not in frequent.columns
    assert "affected_row_count" not in frequent.columns

    issues = next(frame for frame in frames if "Explanation" in frame.columns)
    assert len(issues) == 18
    assert list(issues.columns)[:8] == [
        "Severity",
        "Rule ID",
        "Rule",
        "Explanation",
        "Source row",
        "Record ID",
        "Field",
        "Original value",
    ]

    labels = [button.label for item in app.download_button for button in [item]]
    assert "Download quality summary" in labels
    assert "Download quality issues" in labels
    assert "Download affected records" in labels
    assert "Download rule summary" in labels

    text = _visible_text(app)
    assert "Severity" in text
    assert "Field" in text
    assert "Rule" in text


def test_top_ten_overview_uses_catalog_tie_order() -> None:
    from production_quality.data import load_production_data
    from streamlit_app import inspect_dataset, top_error_problems

    data = load_production_data(PROJECT_ROOT / "data" / "production_data.csv")
    bundle = inspect_dataset(data)
    display = top_error_problems(bundle.rules)
    assert list(display["Problem"]) == TOP_TEN_LABELS
    assert list(display["Chart label"]) == TOP_TEN_CHART_LABELS
    assert list(display["Findings"]) == TOP_TEN_FINDINGS
    assert len(display) == 10
    assert bundle.complete.error_count == 18
    assert bundle.complete.affected_row_count == 17
    assert len(bundle.issues) == 18
    assert list(bundle.issues.columns)[0] == "severity"


def test_overview_chart_spec_keeps_short_labels_and_full_tooltip() -> None:
    from streamlit_app import (
        OVERVIEW_BAR_SIZE,
        OVERVIEW_CATEGORY_STEP,
        overview_chart_spec,
    )

    spec = overview_chart_spec(TOP_TEN_CHART_LABELS)
    bar = spec["layer"][0]
    assert spec["height"] == OVERVIEW_CATEGORY_STEP * len(TOP_TEN_CHART_LABELS)
    assert bar["mark"]["size"] == OVERVIEW_BAR_SIZE
    assert bar["encoding"]["y"]["sort"] == TOP_TEN_CHART_LABELS
    assert bar["encoding"]["y"]["title"] is None
    assert bar["encoding"]["x"]["scale"]["domainMin"] == 0
    tooltip = bar["encoding"]["tooltip"]
    assert [item["field"] for item in tooltip] == [
        "Problem",
        "Findings",
        "Affected rows",
    ]
    assert [item["title"] for item in tooltip] == [
        "Problem",
        "Error findings",
        "Affected rows",
    ]
