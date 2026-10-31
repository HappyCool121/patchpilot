"""Static HTML chrome for the Streamlit UI. Model and pytest text never pass through here."""

from html import escape
from pathlib import Path

STATIC = Path(__file__).parent / "static"

STEPS = (
    ("REPRODUCING", "Reproduce", "Daytona runs the original tests"),
    ("PROPOSING", "Propose", "Nosana drafts one edit"),
    ("APPLYING", "Apply", "Validated edit enters the sandbox"),
    ("VERIFYING", "Verify", "The identical tests rerun"),
)
STEP_LABELS = {
    "pending": "Waiting",
    "active": "Running",
    "done": "Done",
    "warn": "Still failing",
    "failed": "Failed",
    "skipped": "Skipped",
}
VERDICTS = {
    "VERIFIED": ("verified", "Verified.",
                 "The baseline failed, the edit was applied, and the same tests now pass."),
    "NOT_VERIFIED": ("not-verified", "Not verified.",
                     "The edit was applied, but the rerun still reports test failures."),
    "NO_FAILURE_REPRODUCED": ("no-failure", "No failure reproduced.",
                              "The baseline already passed, so no repair was requested."),
    "ERROR": ("error", "Error.",
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
            '<p class="pp-hero__body">Daytona runs the code. Nosana proposes one constrained edit. '
            'You review the diff and the test evidence.</p>'
            '<div class="pp-note">' + chip("Seeded demo defect") +
            '<p>The discount formula in <code>discount.py</code> is intentionally wrong. '
            'A price of 100 with a 20% discount must produce 80.</p></div></section>')


def provider_chips(checks):
    def provider(name, ok, detail):
        tone = "ok" if ok else "error"
        return (f'<span class="pp-provider pp-provider--{tone}"><span class="pp-dot"></span>'
                f'<b>{name}</b><span>{escape(detail)}</span></span>')
    nosana = checks.get("Nosana model")
    daytona = checks.get("Daytona")
    return ('<div class="pp-providers">'
            + provider("Nosana", nosana is not None, nosana or "Check failed")
            + provider("Daytona", daytona is not None, daytona or "Check failed")
            + "</div>")


def step_states(stages):
    """Map the recorded run stages onto the four tracker steps."""
    last = stages[-1] if stages else None
    finished = last in VERDICTS
    states = []
    for key, _, _ in STEPS:
        if key not in stages:
            states.append("skipped" if finished else "pending")
        elif not finished and key == last:
            states.append("active")
        elif last == "ERROR" and key == stages[-2]:
            states.append("failed")
        elif last == "NOT_VERIFIED" and key == "VERIFYING":
            states.append("warn")
        else:
            states.append("done")
    return states


def stage_tracker(stages):
    cells = []
    for index, ((_, name, hint), state) in enumerate(zip(STEPS, step_states(stages)), 1):
        cells.append(f'<div class="pp-step pp-step--{state}" role="listitem">'
                     f'<span class="pp-step__index">{index:02d}</span>'
                     f'<span class="pp-step__name">{name}</span>'
                     f'<span class="pp-step__hint">{hint}</span>'
                     f'<span class="pp-step__state">{STEP_LABELS[state]}</span></div>')
    return f'<div class="pp-tracker" role="list" aria-label="Repair stages">{"".join(cells)}</div>'


def verdict_banner(run):
    tone, title, meaning = VERDICTS.get(run["state"], VERDICTS["ERROR"])
    meta = [("Run", run["id"]), ("Sandbox", run["sandbox_id"] or "not created")]
    if run.get("trace") and run["trace"].get("model"):
        meta.append(("Model", run["trace"]["model"]))
    if run["cleanup_error"]:
        meta.append(("Cleanup", "failed"))
    elif run["cleanup_complete"]:
        meta.append(("Cleanup", "complete"))
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


def empty_state():
    return ('<div class="pp-empty">' + stage_tracker([]) +
            '<p>No run yet. Press <b>Repair demo bug</b> to reproduce the failure in a fresh sandbox.</p></div>')
