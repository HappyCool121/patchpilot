"""HTML chrome: tracker states, verdict tones and escaping."""

import json

import pytest

from patchpilot import core, view

FULL = ["reproducing", "investigating", "proposing", "applying", "verifying", "done"]
NO_GRAPH = ["reproducing", "proposing", "applying", "verifying", "done"]


@pytest.mark.parametrize("stages, verdict, graph_status, expected", [
    ([], None, "", ["pending"] * 5),
    (["reproducing", "reproducing"], None, "", ["active"] + ["pending"] * 4),
    (["reproducing", "proposing"], None, "", ["done", "optional", "active", "pending", "pending"]),
    (FULL, core.VERIFIED, "connected: 3 related row(s) found", ["done"] * 5),
    (NO_GRAPH, core.VERIFIED, "not configured (repair continues without graph context)",
     ["done", "optional", "done", "done", "done"]),
    (FULL, core.VERIFIED, "unavailable (ServiceUnavailable: x); repair continues",
     ["done", "warn", "done", "done", "done"]),
    (NO_GRAPH, core.NOT_VERIFIED, "not configured", ["done", "optional", "done", "done", "warn"]),
    (["reproducing", "done"], core.NO_FAILURE, "not used", ["done"] + ["skipped"] * 4),
    (["reproducing", "done"], core.ERROR, "not used", ["failed"] + ["skipped"] * 4),
    (["reproducing", "proposing", "done"], core.ERROR, "not configured",
     ["done", "optional", "failed", "skipped", "skipped"]),
])
def test_step_states(stages, verdict, graph_status, expected):
    assert view.step_states(stages, verdict, graph_status) == expected


def test_tracker_renders_every_step():
    html = view.stage_tracker(["reproducing"])
    assert html.count('role="listitem"') == 5 and "pp-step--active" in html


def make_run(**overrides):
    run = core.Run(model="test-model", sandbox_id="sandbox-id", cleanup="sandbox deleted",
                   graph_status="not configured (repair continues without graph context)")
    for key, value in overrides.items():
        setattr(run, key, value)
    return run


@pytest.mark.parametrize("verdict, tone", [
    (core.VERIFIED, "verified"), (core.NOT_VERIFIED, "not-verified"),
    (core.NO_FAILURE, "no-failure"), (core.ERROR, "error"), (None, "error")])
def test_verdict_tones(verdict, tone):
    assert f"pp-verdict--{tone}" in view.verdict_banner(make_run(verdict=verdict))


def test_dynamic_values_are_escaped():
    hostile = "<img src=x onerror=alert(1)>"
    html = view.verdict_banner(make_run(verdict=core.VERIFIED, sandbox_id=hostile, model=hostile))
    html += view.provider_chips([("Nosana", "error", hostile)])
    assert "<img" not in html and "&lt;img" in html


def test_cleanup_and_graph_summary():
    html = view.verdict_banner(make_run(verdict=core.VERIFIED))
    assert "sandbox deleted" in html and "not configured" in html
    failed = view.verdict_banner(make_run(verdict=core.VERIFIED, cleanup="CLEANUP FAILED (X); delete"))
    assert "<b>Cleanup</b>failed" in failed


def test_exit_chip_tones():
    assert "pp-exit--pass" in view.exit_chip(0)
    assert "pp-exit--fail" in view.exit_chip(1)
    assert "pp-exit--error" in view.exit_chip(None)


def test_run_evidence_is_json_and_skips_callback():
    run = make_run(verdict=core.VERIFIED, on_event=lambda *a: None)
    run.log("done", "Verdict: VERIFIED")
    evidence = view.run_evidence(run)
    assert "on_event" not in evidence
    assert json.loads(json.dumps(evidence))["verdict"] == core.VERIFIED
