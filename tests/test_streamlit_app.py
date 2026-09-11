"""Tests for the Streamlit dashboard shell."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "streamlit_app.py"


def test_app_starts_without_an_exception() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert not app.exception


def test_page_title_and_english_workflow_are_visible() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert any("Production Data Quality Inspector" in title.value for title in app.title)
    markdown = " ".join(item.value for item in app.markdown)
    assert "Choose a data source" in markdown
    assert "Run the quality inspection" in markdown
    assert "Download the reports" in markdown


def test_data_source_selector_and_actions_exist() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    radio_labels = " ".join(" ".join(map(str, widget.options)) for widget in app.radio)
    assert "Upload a CSV" in radio_labels
    assert "Use demonstration dataset" in radio_labels
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
    body = " ".join(
        [
            *(item.value for item in app.title),
            *(item.value for item in app.markdown),
            *(str(item.value) for item in app.info),
            *(str(item.value) for item in app.error),
            *(str(item.value) for item in app.success),
            *(str(item.value) for item in app.warning),
            *(f"{item.label} {item.value}" for item in app.metric),
        ]
    )
    assert "Issues found" in body
    assert "98.58%" in body
    assert "1,200" in body or "1200" in body
    assert "17" in body
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
