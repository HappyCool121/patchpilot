"""Launch with: streamlit run patchpilot/ui.py"""

import json
import os

import streamlit as st

from patchpilot import view
from patchpilot.core import execute, sources
from patchpilot.providers import DaytonaSandbox, NosanaModel, redact

PROGRESS = {
    "REPRODUCING": "Reproducing the failure in a fresh Daytona sandbox…",
    "PROPOSING": "Requesting one repair from Nosana…",
    "APPLYING": "Validating and applying the edit…",
    "VERIFYING": "Rerunning the identical tests…",
}

st.set_page_config(page_title="PatchPilot", page_icon=str(view.STATIC / "patchpilot-logo.svg"), layout="wide")
st.logo(str(view.STATIC / "patchpilot-lockup.svg"), size="large")
st.html(view.style())
st.html(view.hero())
with st.expander("View original implementation and read-only tests"):
    for path, text in sources().items():
        st.caption(path)
        st.code(text, language="python")

missing = [name for name in ("DAYTONA_API_KEY", "NOSANA_API_KEY") if not os.environ.get(name)]
st.html(view.section_heading("Run", "Repair the seeded bug."))
if missing:
    st.warning("Configure server environment variables: " + ", ".join(missing))


@st.cache_resource(ttl=300)
def check_access():
    model = NosanaModel()
    checks = {}
    try:
        checks["Nosana model"] = model.discover()
    except Exception as exc:
        checks["Nosana error"] = redact(str(exc))[:1000]
    try:
        box = DaytonaSandbox()
        client = box.connect()
        # Read-only API check; no billable sandbox is created by this check.
        next(client.list(request_timeout=15), None)
        checks["Daytona"] = "Sandbox API reachable"
    except Exception as exc:
        checks["Daytona error"] = redact(str(exc))[:1000]
    return checks, model


model = None
if not missing:
    with st.spinner("Checking provider access…"):
        checks, model = check_access()
    st.html(view.provider_chips(checks))
    if any("error" in key for key in checks):
        with st.expander("Provider check details", expanded=True):
            st.json(checks)

with st.container(horizontal=True, gap="small"):
    repair = st.button("Repair demo bug", type="primary", disabled=bool(missing))
    if not missing and st.button("Refresh provider checks"):
        check_access.clear()
        st.rerun()

if repair:
    # Replace the latest run; no history database, automatic retries or API service.
    with st.status("Starting fresh sandbox…", expanded=True) as status:
        stages = []
        tracker = st.empty()
        tracker.html(view.stage_tracker(stages))

        def progress(state):
            stages.append(state)
            status.update(label=PROGRESS.get(state, state.replace("_", " ").capitalize()))
            tracker.html(view.stage_tracker(stages))

        run = execute(DaytonaSandbox(), model, progress, redact)
        st.session_state["latest_run"] = run
        status.update(label=run["state"].replace("_", " ").capitalize(),
                      state="error" if run["state"] == "ERROR" else "complete", expanded=False)

run = st.session_state.get("latest_run")
if not run:
    st.html(view.empty_state())
else:
    st.html(view.verdict_banner(run))
    if run["error"]:
        st.error(run["error"])
    if run["cleanup_error"]:
        st.warning("Sandbox cleanup failed. Retain the sandbox ID above and delete it in Daytona. " + run["cleanup_error"])
    st.html(view.stage_tracker(run["stages"]))

    if run["proposal"]:
        st.html(view.section_heading("Nosana proposal", "Diagnosis and edit."))
        with st.container(key="pp-proposal"):
            st.html(view.panel_label("Diagnosis"))
            st.text(run["proposal"]["diagnosis"])
            st.html(view.panel_label("Explanation"))
            st.text(run["proposal"]["explanation"])
            st.html(view.panel_label("Unified diff", view.chip("discount.py only")))
            st.code(run["diff"], language="diff")

    st.html(view.section_heading("Daytona evidence", "Before and after."))
    before, after = st.columns(2, gap="medium")
    for column, key, label, result in ((before, "pp-before", "Before repair", run["baseline"]),
                                       (after, "pp-after", "After repair", run["verification"])):
        with column, st.container(key=key):
            st.html(view.panel_label(label, view.exit_chip(result["exit_code"]) if result else ""))
            if result:
                st.code(result["command"], language="bash")
                st.code(result["output"], language="text")
            else:
                st.html('<p class="pp-muted">Not executed or no valid completed result.</p>')

    if run["trace"]:
        with st.expander("Real inference request and response evidence"):
            st.json(run["trace"])
    st.download_button("Download run evidence", data=json.dumps(run, indent=2),
                       file_name=f"patchpilot-{run['id']}.json", mime="application/json")
st.caption("VERIFIED means the designated tests passed after the edit. Review the patch before use. Each manual run starts from the original fixture; only the latest run is retained in this session.")
