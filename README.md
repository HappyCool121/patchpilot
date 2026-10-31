# PatchPilot

From a failing test to an AI-proposed, sandbox-verified patch, with the evidence visible.

PatchPilot runs one complete repair cycle on a prepared Python fixture: **Daytona** reproduces
the failing tests in an isolated sandbox, **Neo4j** (optional) maps the failing tests to the code
they exercise, a model served by **Nosana** proposes a small structured fix, PatchPilot validates
and applies it inside the sandbox, and Daytona reruns the same unchanged tests. The verdict comes
from the test results, never from the model. The spec is in [mvp.md](mvp.md).

The repair engine (`patchpilot/core.py`, fixture and `tests/test_core.py`) is ported unchanged
from [Viamance/patchpilot67](https://github.com/Viamance/patchpilot67); the one-screen UI is
styled to match the PatchPilot landing page.

## Running the demo

### 1. Prerequisites

- Python 3.12 or newer, git, and a modern browser.
- A **Daytona** account with an API key (app.daytona.io/dashboard/keys).
- A **Nosana** API key with `inference:use` permission and usable credits (deploy.nosana.com).
  Each run makes exactly one model request.
- Optional: a **Neo4j** instance (an AuraDB Free instance works). The demo runs fully without it.
- Network access from your machine to Daytona and `inference.nosana.com`. The Daytona sandbox
  needs internet access to PyPI if its image does not already include pytest.

### 2. Install

```sh
git clone https://github.com/HappyCool121/patchpilot.git
cd patchpilot
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

### 3. Configure keys

Copy the example settings file and keep it private:

```sh
cp .env.example .env
chmod 600 .env
```

Fill in `.env`. It is gitignored, and the app loads it automatically from the directory you
launch in. To enter keys without them appearing on screen or in shell history (zsh):

```sh
read -rs "DK?Daytona API key: "; echo
read -rs "NK?Nosana API key: "; echo
sed -i '' "s|^DAYTONA_API_KEY=.*|DAYTONA_API_KEY=$DK|; s|^NOSANA_API_KEY=.*|NOSANA_API_KEY=$NK|" .env
unset DK NK
```

On Linux, use `sed -i` instead of `sed -i ''`. To check which settings are filled in without
printing them: `sed -E 's/=(.+)/=<set>/' .env`.

| Setting | Required | Notes |
| --- | --- | --- |
| `DAYTONA_API_KEY` | yes | Creates and deletes the sandbox. |
| `NOSANA_API_KEY` | yes | Needs `inference:use` and credits. |
| `NOSANA_MODEL` | no | Preselected in the model picker. `qwen/qwen3.8-27b` is known to work. |
| `DAYTONA_TARGET` | no | `us` (default) or `eu`. |
| `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` | no | All three enable graph context. Use `neo4j+ssc://` instead of `neo4j+s://` if your network breaks certificate checks. |

Never commit `.env` or show keys in a recording.

### 4. Launch

Run from the checkout root, so that `.env` and the dark theme in `.streamlit/config.toml` load:

```sh
.venv/bin/streamlit run patchpilot/ui.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501. Keep the app on loopback, or put authentication in front of it before
exposing a server that spends provider credits.

### 5. Run a repair

1. Expand **View original implementation and read-only tests** to show the seeded bug:
   `apply_discount` in `pricing.py` returns the discount amount instead of the discounted price.
2. Pick a chat model under **Nosana model**. Embedding and reranking models are filtered out.
   Use **Refresh models** if the list looks stale.
3. Click **Repair demo bug** and watch the tracker:
   - **Reproduce:** a fresh Daytona sandbox receives the fixture and runs `python -m pytest -q`.
   - **Investigate** (only with Neo4j): the code graph and failures are written to Neo4j and
     queried for context. Without Neo4j this step is skipped and the run continues.
   - **Propose:** one Nosana request returns a diagnosis and one structured edit.
   - **Apply:** the edit is validated and applied to `pricing.py` inside the sandbox.
   - **Verify:** the same command reruns against the original, unchanged tests.
4. Read the result: the verdict, diagnosis, diff, and before/after test output.
5. Open **Run evidence and event log** and click **Download run evidence** to save the run as
   JSON. Only the latest run is kept in the session, so download before starting another.

### 6. Read the verdict

| Verdict | Meaning |
| --- | --- |
| **VERIFIED** | Baseline failed (exit 1), the edit was applied, and the rerun passed (exit 0). |
| **NOT VERIFIED** | The edit was applied but tests still fail (exit 1). Nothing is retried. |
| **NO FAILURE REPRODUCED** | Baseline already passed. No model request is made. |
| **ERROR** | Setup, provider, timeout, rejected edit, or a pytest exit code other than 0 or 1. |

VERIFIED means the designated tests passed after the patch; it does not prove the code is
correct in general. The sandbox is deleted on every path. If deletion fails, the screen says so
and shows the sandbox ID for manual cleanup in the Daytona dashboard.

### 7. Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `KeyError: 'DAYTONA_API_KEY'` or similar | `.env` missing or the app was launched outside the checkout root. |
| Nosana model list failed | Wrong key, missing `inference:use` permission, or network blocked. |
| `400 Bad Request` from Nosana | The selected model does not support chat. Pick another model. |
| "model returned an empty answer" | The model produced only reasoning text. Pick another model. |
| "proposal rejected, nothing applied" | The model's JSON broke a rule (wrong file, more than one edit, `old` snippet not found exactly once). Run again or try another model. |
| pytest could not be installed | The sandbox has no internet access. Use a Daytona image with pytest preinstalled. |
| Neo4j unavailable | Check the three `NEO4J_*` settings. The repair continues without graph context either way. |

Stop the app with Ctrl+C in its terminal.

## How it works

1. A fresh Daytona sandbox receives `patchpilot/fixture/pricing.py` and `test_pricing.py`.
2. Baseline: `python -m pytest -q` (pytest is installed in the sandbox if missing). Exit 0 stops
   with **NO FAILURE REPRODUCED**; any code other than 1 is an **ERROR**.
3. Neo4j (optional): the fixture's files, functions, imports and test targets are read with
   Python's `ast` module and stored as `(File)-[:DEFINES]->(Function)`,
   `(File)-[:IMPORTS]->(File)` and `(Test)-[:TARGETS]->(Function)`; each failing test becomes
   `(Failure)-[:OCCURS_IN]->(Test)`. One Cypher query returns each failing test, the function it
   targets, its file, and how many verified repairs that file has had. The query and rows are shown
   on screen and added to the model prompt. After the rerun, `(Repair)-[:MODIFIES]->(File)` and
   `(Repair)-[:ADDRESSES]->(Failure)` record the outcome. If Neo4j is missing or fails, the run
   continues and says so.
4. One Nosana request returns JSON with `diagnosis`, `explanation` and one edit (`path`, `old`,
   `new`). Markdown fences around the JSON are tolerated.
5. The edit is rejected unless it targets `pricing.py` only, is non-empty, and its `old` snippet
   matches exactly once. Tests are never modified, and no model-supplied command is ever run.
6. The edit is applied inside the sandbox, the original tests are re-uploaded, and the same command
   reruns.
7. Exit 0 is **VERIFIED**, exit 1 is **NOT VERIFIED**, anything else is **ERROR**. The sandbox is
   deleted on every path, and a cleanup failure is reported separately with the sandbox ID.

The local fixture file is only read, never written, so every run starts from the original bug.

## From demo to a real implementation

The demo deliberately fixes one prepared bug. The pipeline itself (reproduce, propose, validate,
apply, verify, clean up) is the part worth keeping; most of the work is replacing the places where
the demo is hard-coded. None of the following is implemented yet.

### What is fixed in the demo today

- **Target code:** `load_fixture()` reads two bundled files, and `IMPL_FILE`, `TEST_FILE` and
  `ALLOWED_PATHS` in `core.py` name them directly.
- **Prompt:** `build_messages()` hard-codes `pricing.py` and `test_pricing.py` and sends both
  files whole.
- **Validation:** `validate_proposal()` accepts exactly one edit to one allowlisted file.
- **Attempts:** one model request per run, with no feedback loop.
- **Output:** the diff and evidence stay in the Streamlit session; nothing is written back.

### Suggested path

1. **Run on real repositories.** Clone the target repository and commit inside the Daytona
   sandbox instead of uploading the fixture, using a short-lived, read-only token for private
   repositories. Install dependencies from the project's own manifest (`requirements.txt`,
   `pyproject.toml`, a lockfile), ideally from a prebuilt Daytona snapshot per project to keep
   runs fast and repeatable.
2. **Target the failure precisely.** Let the user (or CI) name the failing test or test command,
   then use pytest's node IDs to rerun just those tests first and the wider suite afterwards, so
   a fix cannot pass its own test while breaking others.
3. **Build context instead of sending whole files.** Real repositories do not fit in a prompt.
   Use the traceback to find the relevant files, and extend the existing Neo4j code graph from
   one fixture to the whole repository (files, functions, imports, test targets, past repairs) so
   the prompt gets only the neighbourhood of the failure. The current graph schema already has
   the right shape for this.
4. **Allow larger but still constrained edits.** Accept several edits across several files, with
   the allowlist derived from the code the failing tests reach rather than a fixed set. Keep the
   hard rules: never edit tests, never run model-supplied commands, `old` snippets must match
   exactly.
5. **Iterate within a budget.** Feed a failed rerun's output back to the model for a bounded
   number of attempts (for example three), with per-run limits on tokens, time and cost. Record
   every attempt in the evidence.
6. **Deliver a reviewable change.** Open a pull request with the diagnosis, diff and before/after
   test output, rather than changing code directly. Keep a human approval step; automatic merging
   stays out of scope.
7. **Trigger from where failures happen.** Add a CI webhook (for example a GitHub Action on a
   failed test job) and a small API, alongside or instead of the Streamlit screen.
8. **Persist and learn.** Store runs and evidence in a database, and keep the Neo4j repair history
   so repeated failures in the same area can reuse what worked before.
9. **Harden for production.** User authentication and per-team API keys held in a secrets manager,
   restricted network egress from sandboxes, sandbox time and resource limits, audit logs, and
   cost tracking per run.
10. **Evaluate models.** Keep a benchmark of seeded bugs and compare Nosana models on verified-fix
    rate, cost and time before changing the default.
11. **Other languages.** The pipeline is language-neutral apart from the test command, verdict
    mapping and code-graph parser, which would each need a per-language adapter.

## Tests

```sh
.venv/bin/python -m pytest -q
```

`tests/test_core.py` covers proposal validation, verdict mapping and the full run flow against a
local fake sandbox (real pytest, fake providers), including Neo4j failing at each step.
`tests/test_view.py` covers the tracker states, verdict styling and HTML escaping, and
`tests/test_ui.py` renders the screen with Streamlit's AppTest for each verdict. They test the
logic only; they are not evidence of live Daytona, Nosana or Neo4j integration.

## Integration status

- Daytona and Nosana: this engine completed a live end-to-end run (VERIFIED) in patchpilot67.
  A live rerun of the ported engine in this repository is pending.
- Neo4j: implemented as optional graph context, added after the MVP spec (mvp.md lists it as
  deferred); live run pending verification.
