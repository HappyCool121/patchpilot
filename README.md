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

## Setup

Requires Python 3.12+. From the checkout root:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

Copy `.env.example` to `.env` (gitignored; loaded automatically) and fill in:

- `DAYTONA_API_KEY`: from app.daytona.io/dashboard/keys
- `NOSANA_API_KEY`: from deploy.nosana.com, needs `inference:use` permission and usable credits
- `NOSANA_MODEL` (optional): preselected in the model picker; `qwen/qwen3.8-27b` is known to work
- `DAYTONA_TARGET` (optional): `us` (default) or `eu`
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` (optional): an AuraDB Free instance works.
  Without them the repair runs without graph context.

Never commit `.env`.

## Run

```sh
.venv/bin/streamlit run patchpilot/ui.py --server.address 127.0.0.1
```

The dark theme lives in `.streamlit/config.toml` and loads when launching from the checkout root;
`patchpilot/static/style.css` adds the remaining styling. Pick a currently served Nosana chat model
(embedding and reranking models are filtered out), then click **Repair demo bug**. Keep the app on
loopback, or authenticate access before exposing a server that spends provider credits.

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
The screen shows a five-step tracker, the verdict, Neo4j context, the diagnosis and diff, and the
before/after test output; **Download run evidence** saves every recorded field as JSON.

**Seeded demo defect:** `apply_discount` returns the discount amount instead of the discounted price.

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

VERIFIED means the designated tests passed after the patch; it does not prove arbitrary code is correct.
