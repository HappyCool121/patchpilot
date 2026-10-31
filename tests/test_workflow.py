import copy
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from patchpilot.core import Result, execute, sources, validate_proposal

RED = Result(1, "FAILED test_discount.py::test_normal_discount\n3 failed in 0.01s")
GREEN = Result(0, "3 passed in 0.01s")
FIX = {"diagnosis": "Discount is subtracted from the original price.",
       "explanation": "Multiply by the remaining fraction.", "edits": [
           {"path": "discount.py", "old": "price * (percent / 100)",
            "new": "price * (1 - percent / 100)"}]}


class Sandbox:
    id = "test-double-sandbox"

    def __init__(self, results):
        self.results = iter(results)
        self.closed = False
        self.writes = []
        self.test_calls = 0

    def prepare(self, files):
        self.files = dict(files)

    def test(self):
        self.test_calls += 1
        return next(self.results)

    def write(self, path, source):
        self.writes.append((path, source))

    def close(self):
        self.closed = True


class Model:
    def __init__(self, payload=FIX):
        self.payload, self.calls = payload, 0

    def propose(self, *args):
        self.calls += 1
        return copy.deepcopy(self.payload), {"model": "test-double"}


class WorkflowTests(unittest.TestCase):
    def run_case(self, results, model=None):
        box, model = Sandbox(results), model or Model()
        run = execute(box, model)
        self.assertTrue(box.closed)
        self.assertTrue(run["cleanup_complete"])
        return run, box, model

    def test_verified_with_unchanged_tests_and_single_attempt(self):
        original = sources()
        run, box, model = self.run_case([RED, GREEN])
        self.assertEqual(run["state"], "VERIFIED")
        self.assertEqual(model.calls, 1)
        self.assertEqual(box.test_calls, 2)
        self.assertEqual([p for p, _ in box.writes], ["discount.py"])
        self.assertEqual(sources(), original)
        self.assertEqual(run["baseline"]["command"], run["verification"]["command"])
        self.assertEqual(run["sandbox_id"], box.id)

    def test_nonfix_does_not_retry(self):
        run, _, model = self.run_case([RED, RED])
        self.assertEqual(run["state"], "NOT_VERIFIED")
        self.assertEqual(model.calls, 1)

    def test_green_baseline_stops_before_model(self):
        run, box, model = self.run_case([GREEN])
        self.assertEqual(run["state"], "NO_FAILURE_REPRODUCED")
        self.assertEqual(model.calls, 0)
        self.assertFalse(box.writes)

    def test_invalid_patch_preserves_trace_and_never_writes(self):
        payload = copy.deepcopy(FIX)
        payload["edits"][0]["path"] = "test_discount.py"
        run, box, _ = self.run_case([RED], Model(payload))
        self.assertEqual(run["state"], "ERROR")
        self.assertIsNotNone(run["trace"])
        self.assertFalse(box.writes)

    def test_provider_failure(self):
        class Broken(Model):
            def propose(self, *args):
                raise TimeoutError("Provider unavailable")
        run, _, _ = self.run_case([RED], Broken())
        self.assertEqual(run["state"], "ERROR")
        self.assertIn("Provider unavailable", run["error"])

    def test_collection_error_and_zero_tests_cannot_verify(self):
        for result in (Result(2, "collection error"), Result(0, "no tests ran"),
                       Result(1, "no tests ran"), Result(None, "3 passed")):
            with self.subTest(result=result):
                run, _, _ = self.run_case([RED, result])
                self.assertEqual(run["state"], "ERROR")

    def test_failed_setup_still_cleans_up(self):
        box = Sandbox([])
        def fail(_):
            raise RuntimeError("upload failed")
        box.prepare = fail
        run = execute(box, Model())
        self.assertTrue(box.closed)
        self.assertEqual(run["sandbox_id"], box.id)
        self.assertEqual(run["state"], "ERROR")

    def test_cleanup_failure_does_not_destroy_evidence(self):
        box = Sandbox([RED, GREEN])
        def fail():
            raise RuntimeError("delete failed")
        box.close = fail
        run = execute(box, Model())
        self.assertEqual(run["state"], "VERIFIED")
        self.assertEqual(run["cleanup_error"], "delete failed")
        self.assertFalse(run["cleanup_complete"])
        self.assertIsNotNone(run["verification"])

    def test_redaction_covers_nested_evidence(self):
        run = execute(Sandbox([RED, GREEN]), Model(), redact=lambda s: s.replace("test-double", "REDACTED"))
        self.assertEqual(run["trace"]["model"], "REDACTED")


class PatchTests(unittest.TestCase):
    def test_diff_and_source(self):
        changed, diff = validate_proposal(FIX, sources())
        self.assertIn("1 - percent", changed)
        self.assertIn("--- a/discount.py", diff)

    def test_paths(self):
        for path in ("test_discount.py", "../discount.py", "/discount.py", "x/../discount.py", "conftest.py"):
            payload = copy.deepcopy(FIX)
            payload["edits"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_proposal(payload, sources())

    def test_invalid_edits(self):
        for old, new in (("price", "x"), ("absent", "x"), ("price", "price"),
                         (FIX["edits"][0]["old"], "(("), ("", "x"), ("return", "")):
            payload = copy.deepcopy(FIX)
            payload["edits"][0].update(old=old, new=new)
            with self.subTest(old=old), self.assertRaises((ValueError, SyntaxError)):
                validate_proposal(payload, sources())

    def test_schema_and_exactly_one_edit(self):
        for payload in (None, {}, {**FIX, "extra": True}, {**FIX, "edits": []},
                        {**FIX, "edits": FIX["edits"] * 2}, {**FIX, "diagnosis": 42}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_proposal(payload, sources())


class UITests(unittest.TestCase):
    def test_missing_configuration_ui(self):
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ, {}, clear=True):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "patchpilot/ui.py")).run(timeout=15)
            self.assertFalse(app.exception)
            self.assertTrue(app.button[0].disabled)
            self.assertIn("DAYTONA_API_KEY", app.warning[0].value)

    def test_single_screen_repair_with_explicit_test_doubles(self):
        from streamlit.testing.v1 import AppTest
        box, model = Sandbox([RED, GREEN]), Model()
        model.discover = lambda: "test-double"
        box.connect = lambda: type("Client", (), {"list": lambda self, **kw: iter([])})()
        with patch.dict(os.environ, {"DAYTONA_API_KEY": "test-only", "NOSANA_API_KEY": "test-only"}), \
             patch("patchpilot.providers.DaytonaSandbox", return_value=box), \
             patch("patchpilot.providers.NosanaModel", return_value=model):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "patchpilot/ui.py")).run(timeout=15)
            repair = next(button for button in app.button if button.label == "Repair demo bug")
            repair.click().run(timeout=15)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["latest_run"]["state"], "VERIFIED")
            self.assertTrue(box.closed)


if __name__ == "__main__":
    unittest.main()
