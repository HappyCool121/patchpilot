"""Static HTML chrome for the Streamlit UI. Model and pytest text never pass through here."""

from dataclasses import fields
from html import escape
from pathlib import Path

from patchpilot.core import ERROR, IMPL_FILE, NO_FAILURE, NOT_VERIFIED, VERIFIED

STATIC = Path(__file__).parent / "static"

STEPS = (
    ("reproducing", "Reproduce", "Daytona runs the original tests"),
    ("investigating", "Investigate", "Neo4j maps the failure to code"),
    ("proposing", "Propose", "Nosana drafts one edit"),
    ("applying", "Apply", "Validated edit enters the sandbox"),
    ("verifying", "Verify", "The identical tests rerun"),
)
STEP_LABELS = {
    "pending": "Waiting",
    "active": "Running",
    "done": "Done",
    "warn": "Check result",
    "failed": "Failed",
    "skipped": "Skipped",
    "optional": "Optional · off",
}
VERDICTS = {
    VERIFIED: ("verified", "Verified.",
               "The baseline failed, the edit was applied, and the same tests now pass."),
    NOT_VERIFIED: ("not-verified", "Not verified.",
                   "The edit was applied, but the rerun still reports test failures."),
    NO_FAILURE: ("no-failure", "No failure reproduced.",
                 "The baseline already passed, so no repair was requested."),
    ERROR: ("error", "Error.",
            "A provider, setup, timeout, edit or execution problem prevented a valid result."),
}


def style():
    return f"<style>{(STATIC / 'style.css').read_text()}</style>"


def chip(text, tone=""):
    return f'<span class="pp-chip{" pp-chip--" + tone if tone else ""}">{escape(text)}</span>'


def hero():
    return ('<section class="pp-hero">' + chip("Seeded Python repair demo") +
            '<h1 class="pp-hero__title"><span>always verifying.</span>'
            '<span class="pp-hero__sub">from failing tests to fixes you can review.</span></h1>'
            '<p class="pp-hero__body">Daytona runs the code. Neo4j, when configured, maps the failure '
            'to the code it exercises. Nosana proposes one constrained edit. '
            'You review the diff and the test evidence.</p>'
            '<div class="pp-note">' + chip("Seeded demo defect") +
            f'<p><code>apply_discount</code> in <code>{IMPL_FILE}</code> returns the discount amount '
            'instead of the discounted price. A price of 100 with a 20% discount must produce 80.</p>'
            '</div></section>')


def provider_chips(providers):
    """providers: (name, tone, detail) with tone ok, error or idle."""
    items = "".join(f'<span class="pp-provider pp-provider--{tone}"><span class="pp-dot"></span>'
                    f'<b>{escape(name)}</b><span>{escape(detail)}</span></span>'
                    for name, tone, detail in providers)
    return f'<div class="pp-providers">{items}</div>'


def step_states(stages, verdict=None, graph_status=""):
    """Map logged run stages onto the tracker steps."""
    keys = [key for key, _, _ in STEPS]
    visited = [stage for stage in dict.fromkeys(stages) if stage in keys]
    last = visited[-1] if visited else None
    states = []
    for index, key in enumerate(keys):
        if key not in visited:
            passed = any(later in visited for later in keys[index + 1:])
            states.append(("optional" if key == "investigating" else "skipped") if passed
                          else "skipped" if verdict else "pending")
        elif verdict is None and key == last:
            states.append("active")
        elif verdict == ERROR and key == last:
            states.append("failed")
        elif key == "investigating" and graph_status.startswith("unavailable"):
            states.append("warn")
        elif verdict == NOT_VERIFIED and key == "verifying":
            states.append("warn")
        else:
            states.append("done")
    return states


def stage_tracker(stages, verdict=None, graph_status=""):
    cells = []
    states = step_states(stages, verdict, graph_status)
    for index, ((_, name, hint), state) in enumerate(zip(STEPS, states), 1):
        cells.append(f'<div class="pp-step pp-step--{state}" role="listitem">'
                     f'<span class="pp-step__index">{index:02d}</span>'
                     f'<span class="pp-step__name">{name}</span>'
                     f'<span class="pp-step__hint">{hint}</span>'
                     f'<span class="pp-step__state">{STEP_LABELS[state]}</span></div>')
    return f'<div class="pp-tracker" role="list" aria-label="Repair stages">{"".join(cells)}</div>'


def graph_summary(status):
    for prefix in ("connected", "not configured", "unavailable", "not used"):
        if status.startswith(prefix):
            return prefix
    return status


def verdict_banner(run):
    tone, title, meaning = VERDICTS.get(run.verdict, VERDICTS[ERROR])
    cleanup = run.cleanup or "no sandbox"
    meta = [("Run", run.run_id), ("Sandbox", run.sandbox_id or "not created"),
            ("Model", run.model or "none"),
            ("Cleanup", "failed" if cleanup.startswith("CLEANUP FAILED") else cleanup),
            ("Neo4j", graph_summary(run.graph_status))]
    items = "".join(f'<span><b>{label}</b>{escape(str(value))}</span>' for label, value in meta)
    return (f'<section class="pp-verdict pp-verdict--{tone}">'
            f'{chip("Verdict", tone)}'
            f'<h2 class="pp-verdict__title">{title}</h2>'
            f'<p class="pp-verdict__meaning">{meaning}</p>'
            f'<div class="pp-meta">{items}</div></section>')


def exit_chip(code):
    tone = {0: "pass", 1: "fail"}.get(code, "error")
    return f'<span class="pp-exit pp-exit--{tone}">exit {escape(str(code))}</span>'


def section_heading(eyebrow, title):
    return f'<div class="pp-section">{chip(eyebrow)}<h2>{escape(title)}</h2></div>'


def panel_label(text, extra=""):
    return f'<div class="pp-panel-label">{chip(text)}{extra}</div>'


def muted(text):
    return f'<p class="pp-muted">{escape(text)}</p>'


def empty_state():
    return ('<div class="pp-empty">' + stage_tracker([]) +
            '<p>No run yet. Pick a model and press <b>Repair demo bug</b> to reproduce the failure '
            'in a fresh sandbox.</p></div>')


def run_evidence(run):
    """Every recorded Run field, ready for json.dumps."""
    return {f.name: getattr(run, f.name) for f in fields(run) if f.name != "on_event"}
