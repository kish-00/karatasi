from __future__ import annotations

from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "src" / "ui" / "app.py"

streamlit = pytest.importorskip("streamlit")


@pytest.fixture
def app_test():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    return at


def test_ui_boots_without_exceptions(app_test) -> None:
    assert len(app_test.exception) == 0
    assert len(app_test.text_input) == 1
    assert len(app_test.button) == 11


def test_ui_suggestion_chip_answers(app_test) -> None:
    app_test.button[0].click()
    app_test.run()
    assert len(app_test.exception) == 0
    history = app_test.session_state["history"]
    assert len(history) == 1
    turn = history[0]
    assert turn["question"]
    assert turn["text"]
    assert turn["files"]


def test_ui_sql_question_via_form(app_test) -> None:
    app_test.text_input[0].set_value("What was invoice AT-2024-0007?")
    app_test.run()
    app_test.button[-1].click()
    app_test.run()
    assert len(app_test.exception) == 0
    turn = app_test.session_state["history"][-1]
    assert turn["route"] == "SQL"
    assert turn["text"] == "8,120.00 USD"
    assert turn["files"] == ["invoice_AT-2024-0007.pdf"]


def test_ui_format_answer_renders_values_and_sources() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("ui_app", APP)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    lines = mod.format_answer(
        {
            "text": "8,120.00 USD",
            "values": [{"currency": "USD", "value": 8120.0}],
            "files": ["invoice_AT-2024-0007.pdf"],
            "route": "SQL",
        }
    )
    assert "8,120.00 USD" in lines[0]
    assert any(line.startswith("**Values:**") for line in lines)
    assert any(line.startswith("**Sources:**") for line in lines)
