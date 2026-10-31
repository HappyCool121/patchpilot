"""Launch with: streamlit run patchpilot/ui.py"""

import json
import os

import streamlit as st

from patchpilot.core import execute, sources
from patchpilot.providers import DaytonaSandbox, NosanaModel, redact

st.set_page_config(page_title="PatchPilot", page_icon="🛠", layout="wide")
st.caption("PATCHPILOT / SEEDED PYTHON REPAIR DEMO")
st.title("A failing test. A proposed fix. The evidence.")
st.write("Daytona runs the code. Nosana proposes one constrained edit. You review the result.")
st.info("Seeded demo defect: a discount formula is intentionally wrong. A price of 100 with a 20% discount must produce 80.")
with st.expander("View original implementation and read-only tests"):
    for path, text in sources().items():
        st.caption(path)
        st.code(text, language="python")

missing = [name for name in ("DAYTONA_API_KEY", "NOSANA_API_KEY") if not os.environ.get(name)]
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
    with st.expander("Provider access checks", expanded=any("error" in k for k in checks)):
        st.json(checks)
    if st.button("Refresh provider checks"):
        check_access.clear()
        st.rerun()

if st.button("Repair demo bug", type="primary", disabled=bool(missing)):
    # Replace the latest run; no history database, automatic retries or API service.
    with st.status("Starting fresh sandbox…", expanded=True) as status:
        def progress(state):
            status.update(label=state.replace("_", " "))
            st.write(state.replace("_", " ").capitalize())
        run = execute(DaytonaSandbox(), model, progress, redact)
        st.session_state["latest_run"] = run
        status.update(label=run["state"].replace("_", " "),
                      state="error" if run["state"] == "ERROR" else "complete", expanded=False)

run = st.session_state.get("latest_run")
if run:
    st.divider()
    st.subheader(run["state"].replace("_", " "))
    st.caption(f"Run {run['id']} · Sandbox {run['sandbox_id'] or 'not created'}")
    if run["error"]:
        st.error(run["error"])
    if run["cleanup_error"]:
        st.warning("Sandbox cleanup failed. Retain the sandbox ID above and delete it in Daytona. " + run["cleanup_error"])
    elif run["cleanup_complete"]:
        st.caption("Sandbox cleanup completed (or no sandbox was created). Evidence is retained below.")
    if run["proposal"]:
        st.subheader("AI proposal")
        st.text(run["proposal"]["diagnosis"])
        st.text(run["proposal"]["explanation"])
        st.code(run["diff"], language="diff")
    before, after = st.columns(2)
    for column, label, result in ((before, "Before repair", run["baseline"]),
                                  (after, "After repair", run["verification"])):
        with column:
            st.subheader(label)
            if result:
                st.code(result["command"], language="bash")
                st.caption(f"Exit code: {result['exit_code']}")
                st.code(result["output"], language="text")
            else:
                st.write("Not executed or no valid completed result.")
    if run["trace"]:
        with st.expander("Real inference request and response evidence"):
            st.json(run["trace"])
    st.download_button("Download run evidence", data=json.dumps(run, indent=2),
                       file_name=f"patchpilot-{run['id']}.json", mime="application/json")
st.caption("VERIFIED means the designated tests passed after the edit. Review the patch before use. Each manual run starts from the original fixture; only the latest run is retained in this session.")
