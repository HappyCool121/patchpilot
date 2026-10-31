import unittest

from patchpilot import view


def run_with(state, **overrides):
    run = {"id": "run-id", "state": state, "sandbox_id": "sandbox-id", "trace": None,
           "cleanup_error": None, "cleanup_complete": True}
    return {**run, **overrides}


class TrackerTests(unittest.TestCase):
    def test_step_states_for_each_path(self):
        cases = {
            (): ["pending"] * 4,
            ("REPRODUCING", "PROPOSING"): ["done", "active", "pending", "pending"],
            ("REPRODUCING", "PROPOSING", "APPLYING", "VERIFYING", "VERIFIED"): ["done"] * 4,
            ("REPRODUCING", "PROPOSING", "APPLYING", "VERIFYING", "NOT_VERIFIED"):
                ["done", "done", "done", "warn"],
            ("REPRODUCING", "NO_FAILURE_REPRODUCED"): ["done", "skipped", "skipped", "skipped"],
            ("REPRODUCING", "ERROR"): ["failed", "skipped", "skipped", "skipped"],
            ("REPRODUCING", "PROPOSING", "APPLYING", "ERROR"): ["done", "done", "failed", "skipped"],
        }
        for stages, expected in cases.items():
            with self.subTest(stages=stages):
                self.assertEqual(view.step_states(list(stages)), expected)

    def test_tracker_renders_every_step(self):
        html = view.stage_tracker(["REPRODUCING"])
        self.assertEqual(html.count('role="listitem"'), 4)
        self.assertIn("pp-step--active", html)


class VerdictTests(unittest.TestCase):
    def test_every_state_has_a_tone(self):
        for state, tone in (("VERIFIED", "verified"), ("NOT_VERIFIED", "not-verified"),
                            ("NO_FAILURE_REPRODUCED", "no-failure"), ("ERROR", "error")):
            with self.subTest(state=state):
                self.assertIn(f"pp-verdict--{tone}", view.verdict_banner(run_with(state)))

    def test_dynamic_values_are_escaped(self):
        hostile = "<img src=x onerror=alert(1)>"
        html = view.verdict_banner(run_with("VERIFIED", sandbox_id=hostile, trace={"model": hostile}))
        html += view.provider_chips({"Nosana model": hostile, "Daytona error": hostile})
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)

    def test_cleanup_status(self):
        self.assertIn("complete", view.verdict_banner(run_with("VERIFIED")))
        failed = view.verdict_banner(run_with("VERIFIED", cleanup_error="x", cleanup_complete=False))
        self.assertIn("failed", failed)

    def test_exit_chip_tones(self):
        self.assertIn("pp-exit--pass", view.exit_chip(0))
        self.assertIn("pp-exit--fail", view.exit_chip(1))
        self.assertIn("pp-exit--error", view.exit_chip(None))


if __name__ == "__main__":
    unittest.main()
