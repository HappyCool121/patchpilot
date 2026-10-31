# PatchPilot

AI-POWERED CODE REPAIR  |  HACKATHON PRODUCT SPECIFICATION  |  V1.0

> PRODUCT PROMISE  From a failing test to a proposed, sandbox-verified fix, with the reasoning and evidence visible to the developer.

## 01  Product overview

Audience  Individual developers, hackathon teams and software engineering teams debugging test failures.

Problem  Developers lose time reading stack traces, tracing cross-file dependencies and manually testing fixes.

Solution  A review-first agent that reproduces an error, retrieves related code context, proposes a minimal repair and reruns the same tests before reporting success.

Business model  Future SaaS subscription (per developer/team) or usage-based pricing per verified attempt; no billing in MVP.

## 02  Sponsor architecture

| Sponsor | MVP integration | Why it matters |
| --- | --- | --- |
| Daytona | Create isolated sandbox; clone demo repo; run failing tests; apply constrained patch; rerun tests; delete sandbox. | Execution and real verification, not simulated success. |
| Neo4j | Store File, Function, Test and Failure nodes with relationships; query the failure neighborhood. | Graph-grounded diagnostics across related code. |
| Nosana | Use hosted, OpenAI-compatible LLM inference to explain root cause and return a structured patch. | Working AI repair model without operating a GPU service. |

## 03  Hackathon MVP: strict scope

| IN: must work in live demo | OUT: after MVP |
| --- | --- |
| One preapproved public Python repo; pytest; one or two seeded bugs; manual Run Repair button. | Private repositories, arbitrary languages, automatic CI webhooks. |
| Real Daytona sandbox and baseline failing test; Neo4j graph query; Nosana model call. | Full-repo embeddings, advanced GraphRAG, code indexing at scale. |
| AI-proposed edit; rerun same test command; show diff, logs and verdict. | Auto-merge, autonomous PR creation, unlimited retry loops. |

## 04  Main user journey

| Step | User-visible behavior / backend event |
| --- | --- |
| 1. Select | Choose fixture repo and permitted test command: python -m pytest -q. |
| 2. Reproduce | Daytona clones into isolated workspace and runs baseline test; capture failing test, traceback and exit status. |
| 3. Investigate | Parse relevant filenames/functions; fetch connected nodes via Neo4j query. |
| 4. Repair | Send bounded context to Nosana; model returns diagnosis + exact file edits in structured JSON. |
| 5. Verify | Validate edit paths, apply patch only in sandbox, rerun the same tests (optionally a broader suite). |
| 6. Review | Display before/after results, unified diff, explanation, linked evidence and VERIFIED / NOT VERIFIED. |

## 05  Functional requirements

| ID / priority | Requirement | Pass condition |
| --- | --- | --- |
| FR-01 / P0 | Kick off a repair run from the web UI. | Run identifier and current stage are visible. |
| FR-02 / P0 | Baseline tests execute in a real Daytona sandbox. | Captured failing exit code and traceback; no fabricated logs. |
| FR-03 / P0 | Relevant code relationships are written to and queried from Neo4j. | At least one real Cypher query appears in run evidence. |
| FR-04 / P0 | Nosana inference returns a proposed code change. | Actual model request/response trace is recorded (without API keys). |
| FR-05 / P0 | Apply a path-validated patch and rerun tests. | Diff plus before/after output are shown. |
| FR-06 / P0 | Report status accurately. | VERIFIED only when baseline fails, the patch is applied and rerun passes. |
| FR-07 / P1 | Show linked files/functions and a concise root-cause explanation. | Graph context appears beside diagnosis. |
| FR-08 / P1 | Allow a second repair attempt after failure. | At most two iterations, both outcomes visible. |

## 06  System design and interfaces

Recommended stack: Next.js or Streamlit UI; Python FastAPI orchestration; Daytona Python SDK; neo4j Python driver (Aura or hosted instance); Nosana inference via OpenAI-compatible Python client. Streamlit is the fastest choice if the team is Python-first.

> DATA FLOW  UI → FastAPI / coordinator → Daytona baseline → Neo4j context retrieval → Nosana repair proposal → Daytona verification → UI result.

### Core backend contract

```text
POST /api/runs    {"repo_id":"demo-python-1"}
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/events
GET  /api/runs/{run_id}/diff
RUN STATES: QUEUED → REPRODUCING → DIAGNOSING → PATCHING →
            VERIFYING → VERIFIED | NOT_VERIFIED | ERROR
```

For the hackathon, a simple in-memory run store and HTTP polling are acceptable; a persistent queue and event streaming are post-MVP. Return stable run IDs and preserve logs until the demo is complete.

### Daytona execution

Use the current stable Python SDK (the v2 SDK has different interfaces and is marked alpha in the published docs). Create a sandbox, clone only a preapproved public fixture, execute the fixed pytest command, inspect stdout/stderr and status, edit allowlisted .py files, rerun tests, then clean up the sandbox in a finally block. Never run repository scripts on the API host.

### Neo4j graph model

```text
(Repository)-[:CONTAINS]->(File)-[:DEFINES]->(Function)
(File)-[:IMPORTS]->(File)
(Test)-[:TARGETS]->(Function)
(Failure)-[:OCCURS_IN]->(Test)
(Repair)-[:MODIFIES]->(File)
(Repair)-[:ADDRESSES]->(Failure)
```

Build nodes from Python AST for functions/imports, pytest output for failures, and known test-to-function mappings for demo fixtures. Retrieve a 1-2 hop neighborhood using parameterized Cypher. Show actual related functions in the UI; store diagnosis and repair outcome to create an explainable history. Neo4j GraphRAG or vector retrieval is optional once basic graph traversal works.

### Nosana inference

Configure NOSANA_API_KEY with inference:use permission. Call https://inference.nosana.com/v1/models at startup; select a currently available chat-capable model ID, then POST a chat completion through the compatible endpoint. Model availability can change; handle empty model lists and capacity errors. No custom Nosana deployment is required for MVP.

```text
INPUT  = failing traceback + permitted file excerpts + graph neighbors
OUTPUT = {"diagnosis":"...", "edits":[{"path":"module.py",
          "old":"original snippet", "new":"replacement snippet"}],
          "explanation":"..."}
```

Treat LLM output as an untrusted suggestion: JSON/schema-validate edits, reject out-of-scope paths, limit patch size, and do not execute model-supplied commands. The model must not claim success; only post-patch test results can establish verification.

## 07  Product UI and result states

| Panel | Minimum contents |
| --- | --- |
| Repository + run | Selected demo repo, Start Repair, run ID and progress rail. |
| Failure evidence | Baseline command, failing test name, stderr excerpt and exit code. |
| Graph context | Related files/functions/tests from real Neo4j lookup; optional graph mini-visual. |
| AI proposal | Diagnosis, explanation and unified diff; label as suggested change. |
| Verification | Second test command/output; status VERIFIED, NOT VERIFIED or ERROR. |

VERIFIED means the designated checks passed after the patch; it is not a guarantee that the code is bug-free. When the baseline unexpectedly passes, show NO FAILURE REPRODUCED and stop rather than manufacturing a bug.

## 08  Reliability, safety and nonfunctional targets

- Sandbox isolation: run all untrusted repository code only inside a disposable Daytona environment; do not mount local secrets into the sandbox.
- Trust boundaries: treat repository README, code comments and model output as untrusted data; never let them override coordinator rules.
- Constrained inputs: use a preapproved public repository list and a fixed pytest command for MVP; avoid arbitrary shell commands or network targets.
- Bounded budgets: target < 3 minutes for the prepared fixture, 2 model attempts maximum, command timeouts, output-size limits and automatic cleanup.
- Failure transparency: expose API/model/clone errors as ERROR, distinguish from a valid test failure, and keep the UI responsive with polling.
- Secret hygiene: keep API keys in server-side environment variables; redact sensitive output; never display full provider credentials.

## 09  Acceptance tests and judge-ready demo

| Scenario | Expected evidence |
| --- | --- |
| Golden-path bug: seeded pure-Python function fails unit test | Baseline red test → Neo4j related-function lookup → Nosana-generated diff → Daytona green test. |
| Non-fix proposal | Second test still fails → NOT VERIFIED; no false success. |
| Provider unavailable / invalid patch | Meaningful ERROR state, bounded retry or safe stop, original repository unchanged. |
| No baseline failure | NO FAILURE REPRODUCED; avoid unnecessary patch. |
| Graph verification | A real Cypher query returning actual node IDs/relationships, not a static screenshot. |

Demo script (roughly 90-120 seconds): show failing fixture → click Repair → highlight Daytona execution logs → display Neo4j relationship → show Nosana diagnosis → display exact diff → rerun tests → finish on verified evidence. Maintain a screen recording of one successful run only as a contingency, not as a substitute for a live integrated path.

## 10  Work split for three builders

| Owner | Primary workstream | Definition of done |
| --- | --- | --- |
| Builder A | Daytona + FastAPI orchestrator; repo clone; test runner; diff; cleanup. | A local API call produces before/after real sandbox logs. |
| Builder B | Neo4j AST graph + Nosana prompt/model adapter + patch validation. | A failure retrieves actual graph context and returns an allowed edit. |
| Builder C | UI, end-to-end integration, demo fixture, QA, pitch and fallback. | Full journey is clickable and failure states are understandable. |

### Delivery sequence

| Priority | Milestone |
| --- | --- |
| First | Get Daytona failing-test reproduction + a basic UI button working end to end. |
| Next | Get Nosana to return a valid patch, apply it, and verify in Daytona; no Neo4j dependency yet. |
| Then | Insert Neo4j graph indexing and context retrieval before the Nosana call; expose evidence. |
| Finish | Polish status/diff panels, run all negative tests, rehearse the pitch and prepare a short backup video. |

## 11  Risks and product roadmap

| Risk | Mitigation |
| --- | --- |
| Model outputs invalid or broad edits | Seed a focused fixture, use file allowlists/schema validation, retry once with failure feedback. |
| Inference availability or credits | Verify Nosana API key/credits/models before implementation; use a currently served model and trim prompt size. |
| Long sandbox provisioning or dependencies | Use a tiny repo with pytest installed in an appropriate image or snapshot; cap wait time. |
| Graph generation consumes hackathon time | Start with 4 node types and a single useful neighborhood query; no graph embedding requirement. |
| Overstated autonomy | Frame product as autonomous proposal + test verification with human review, not production auto-merge. |

Post-MVP: GitHub OAuth/private repos, CI webhook triggers, safe PR creation with approval, richer graph history/GraphRAG, multi-language test templates, regression selection, and cost-aware multi-model repair.

## 12  References / vendor implementation guides

- Daytona Python SDK (stable): <https://www.daytona.io/docs/en/python-sdk/>
- Daytona Git operations: <https://www.daytona.io/docs/en/git-operations/>
- Daytona process execution: <https://www.daytona.io/docs/en/process-code-execution/>
- Neo4j GraphRAG Python: <https://neo4j.com/docs/neo4j-graphrag-python/current/>
- Neo4j GraphRAG retrievers: <https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html>
- Nosana hosted LLM inference: <https://learn.nosana.com/llm/>
- Nosana permissions: <https://learn.nosana.com/api/scopes.html>
