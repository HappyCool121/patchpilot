"""Streamlit screen rendered with AppTest and the offline fakes from test_core.

These check the screen logic only; they are not evidence of live provider integration.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from patchpilot import core
from test_core import BAD_FIX, FakeDaytona, FakeSandbox, GOOD_EDIT, fake_llm, proposal

UI = str(Path(__file__).resolve().parents[1] / "patchpilot/ui.py")


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for key in ("DAYTONA_API_KEY", "NOSANA_API_KEY", "NOSANA_MODEL", "NEO4J_URI", "NEO4J_USERNAME",
                "NEO4J_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    st.cache_data.clear()
    with patch("dotenv.load_dotenv"):  # never read the developer's real .env
        yield


def test_no_models_disables_repair():
    with patch.object(core, "list_models", side_effect=RuntimeError("401 unauthorized")):
        app = AppTest.from_file(UI).run(timeout=15)
    assert not app.exception
    repair = next(b for b in app.button if b.label == "Repair demo bug")
    assert repair.disabled
    assert "401 unauthorized" in app.error[0].value


def repair_with(tmp_path, llm):
    real_run_repair = core.run_repair

    def run_repair(model, on_event=None):
        return real_run_repair(model, on_event=on_event, daytona=FakeDaytona(FakeSandbox(tmp_path)),
                               llm=llm, graph=None)

    with patch.object(core, "list_models", return_value=["test-double-model"]), \
         patch.object(core, "run_repair", side_effect=run_repair):
        app = AppTest.from_file(UI).run(timeout=15)
        assert app.selectbox[0].value == "test-double-model"
        next(b for b in app.button if b.label == "Repair demo bug").click().run(timeout=60)
    assert not app.exception
    return app.session_state["run"]


@pytest.mark.parametrize("edit, verdict", [
    (GOOD_EDIT, core.VERIFIED),
    (BAD_FIX, core.NOT_VERIFIED),
    ({**GOOD_EDIT, "path": "test_pricing.py"}, core.ERROR),
])
def test_repair_renders_each_verdict(tmp_path, edit, verdict):
    run = repair_with(tmp_path, fake_llm(proposal(edit)))
    assert run.verdict == verdict
    assert run.cleanup == "sandbox deleted"
