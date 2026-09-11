"""Tests for the Streamlit dashboard shell."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "streamlit_app.py"
WORKFLOW = "Choose source → Preview → Inspect → Review problems → Download reports"
SCORE_TEXT = "The score shows how many rows have no Error findings."


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
    assert "finding_count" not in frequent.columns
    assert "title" not in frequent.columns
    assert "affected_row_count" not in frequent.columns

    issues = next(frame for frame in frames if "Explanation" in frame.columns)
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
