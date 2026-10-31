import json
import os
import unittest
from unittest.mock import MagicMock, patch

import httpx

from patchpilot.core import sources
from patchpilot.providers import DaytonaSandbox, NosanaModel
from test_workflow import FIX, RED


class AdapterTests(unittest.TestCase):
    def test_daytona_upload_exec_and_delete_contract(self):
        client = MagicMock()
        sandbox = client.create.return_value
        sandbox.id = "sdk-double"
        sandbox.process.exec.return_value.exit_code = 0
        sandbox.process.exec.return_value.result = "3 passed in 0.1s"
        with patch.dict(os.environ, {"DAYTONA_API_KEY": "test-key"}), patch("daytona.Daytona", return_value=client):
            box = DaytonaSandbox()
            box.prepare(sources())
            result = box.test()
            box.close()
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(sandbox.fs.upload_file.call_count, 2)
        sandbox.process.exec.assert_called_with(
            "cd /home/daytona/patchpilot-fixture && python -m pytest -q", timeout=30)
        client.delete.assert_called_once_with(sandbox, timeout=30, wait=True)

    def model_with_transport(self, handler):
        model = NosanaModel()
        model.client = lambda: httpx.Client(base_url="https://inference.nosana.com/v1/",
                                            transport=httpx.MockTransport(handler))
        return model

    def test_nosana_discovers_model_and_calls_completion_once(self):
        calls = []
        def handler(request):
            calls.append(request)
            if request.url.path.endswith("/models"):
                return httpx.Response(200, json={"data": [{"id": "chat-test-double"}]})
            body = json.loads(request.content)
            self.assertEqual(body["model"], "chat-test-double")
            self.assertIn("test_discount.py", body["messages"][1]["content"])
            return httpx.Response(200, json={"id": "response-double", "choices": [
                {"message": {"content": json.dumps(FIX)}}]})
        with patch.dict(os.environ, {}, clear=True):
            model = self.model_with_transport(handler)
            proposal, trace = model.propose(sources(), {"output": RED.output})
        self.assertEqual(proposal, FIX)
        self.assertEqual(trace["model"], "chat-test-double")
        self.assertEqual(len(calls), 2)

    def test_nosana_empty_model_list(self):
        model = self.model_with_transport(lambda request: httpx.Response(200, json={"data": []}))
        with self.assertRaisesRegex(RuntimeError, "no available models"):
            model.discover()

    def test_nosana_capacity_error_no_retry(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(503, json={"error": "capacity"})
        model = self.model_with_transport(handler)
        model.model = "chat-test-double"
        with self.assertRaises(httpx.HTTPStatusError):
            model.propose(sources(), {})
        self.assertEqual(len(requests), 1)


if __name__ == "__main__":
    unittest.main()
