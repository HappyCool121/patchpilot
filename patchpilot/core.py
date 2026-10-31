"""Single-attempt repair workflow; fixture code runs only in Daytona."""

import ast
import difflib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

COMMAND = "python -m pytest -q"
MAX_OUTPUT = 24000
FIXTURE = Path(__file__).parent / "fixture"


def sources():
    return {p.name: p.read_text() for p in sorted(FIXTURE.glob("*.py"))}


@dataclass
class Result:
    exit_code: int
    output: str


@dataclass
class Run:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: str = "QUEUED"
    command: str = COMMAND
    stages: list[str] = field(default_factory=list)
    sandbox_id: str | None = None
    baseline: dict | None = None
    proposal: dict | None = None
    trace: dict | None = None
    diff: str = ""
    verification: dict | None = None
    error: str | None = None
    cleanup_error: str | None = None
    cleanup_complete: bool = False


def validate_proposal(payload, files):
    if not isinstance(payload, dict) or set(payload) != {"diagnosis", "explanation", "edits"}:
        raise ValueError("Proposal must contain diagnosis, explanation and edits")
    for key in ("diagnosis", "explanation"):
        if not isinstance(payload[key], str) or not 1 <= len(payload[key]) <= 6000:
            raise ValueError(f"Invalid {key}")
    edits = payload["edits"]
    if not isinstance(edits, list) or len(edits) != 1:
        raise ValueError("Expected exactly one edit")
    edit = edits[0]
    if not isinstance(edit, dict) or set(edit) != {"path", "old", "new"}:
        raise ValueError("Invalid edit schema")
    path, old, new = edit["path"], edit["old"], edit["new"]
    if not all(isinstance(v, str) for v in (path, old, new)):
        raise ValueError("Edit fields must be strings")
    if path != "discount.py":
        raise ValueError("Only discount.py may change; tests are read-only")
    if not old or not new.strip() or old == new or len(old) + len(new) > 8000:
        raise ValueError("Edit is empty, unchanged or oversized")
    if files[path].count(old) != 1:
        raise ValueError("Old snippet must match exactly once")
    changed = files[path].replace(old, new, 1)
    if len(changed) > 16000:
        raise ValueError("Edited source too large")
    ast.parse(changed)
    diff = "".join(difflib.unified_diff(files[path].splitlines(keepends=True),
                    changed.splitlines(keepends=True), fromfile="a/" + path, tofile="b/" + path))
    if not diff:
        raise ValueError("Empty diff")
    return changed, diff


def checked_result(result):
    if type(result.exit_code) is not int or result.exit_code not in (0, 1):
        raise RuntimeError(f"pytest execution error (exit {result.exit_code})")
    output = result.output[:MAX_OUTPUT]
    expected = "passed" if result.exit_code == 0 else "failed"
    if not re.search(rf"\b[1-9]\d* {expected}\b", output):
        raise RuntimeError("No completed pytest tests matching the exit status")
    if result.exit_code == 0 and re.search(r"\b[1-9]\d* failed\b", output):
        raise RuntimeError("Inconsistent pytest output")
    return {"exit_code": result.exit_code, "output": output, "command": COMMAND}


def execute(sandbox, model, progress=lambda state: None, redact=lambda text: text):
    """Adapters are injected for tests. The application supplies only real providers."""
    run = Run()

    def stage(state):
        run.state = state
        run.stages.append(state)
        progress(state)

    try:
        stage("REPRODUCING")
        files = sources()
        sandbox.prepare(files)
        run.sandbox_id = sandbox.id
        baseline = sandbox.test()
        run.baseline = {"exit_code": baseline.exit_code, "output": baseline.output[:MAX_OUTPUT], "command": COMMAND}
        checked_result(baseline)
        if run.baseline["exit_code"] == 0:
            stage("NO_FAILURE_REPRODUCED")
        else:
            stage("PROPOSING")
            proposal, trace = model.propose(files, run.baseline)
            # Preserve bounded model evidence even when proposal validation fails.
            run.trace = trace
            stage("APPLYING")
            changed, run.diff = validate_proposal(proposal, files)
            run.proposal = proposal
            sandbox.write("discount.py", changed)
            stage("VERIFYING")
            verification = sandbox.test()
            run.verification = {"exit_code": verification.exit_code, "output": verification.output[:MAX_OUTPUT], "command": COMMAND}
            checked_result(verification)
            stage("VERIFIED" if run.verification["exit_code"] == 0 else "NOT_VERIFIED")
    except Exception as exc:
        run.error = f"{type(exc).__name__}: {exc}"[:2000]
        stage("ERROR")
    finally:
        # Also retain the ID when setup failed after creation.
        run.sandbox_id = getattr(sandbox, "id", run.sandbox_id)
        try:
            sandbox.close()
            run.cleanup_complete = True
        except Exception as exc:
            run.cleanup_error = str(exc)[:2000]
    return json.loads(redact(json.dumps(asdict(run))))
