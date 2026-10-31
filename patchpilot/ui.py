"""PatchPilot: one-screen Streamlit app. Launch with: streamlit run patchpilot/ui.py"""

import json
import os

import streamlit as st
from dotenv import load_dotenv

from patchpilot import core, view

PROGRESS = {
    "reproducing": "Reproducing the failure in a fresh Daytona sandbox…",
    "investigating": "Mapping the failure to code in Neo4j…",
    "proposing": "Requesting one repair from Nosana…",
    "applying": "Validating and applying the edit…",
    "verifying": "Rerunning the identical tests…",
}
GRAPH_KEYS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")

load_dotenv()
st.set_page_config(page_title="PatchPilot", page_icon=str(view.STATIC / "patchpilot-logo.svg"), layout="wide")
st.logo(str(view.STATIC / "patchpilot-lockup.svg"), size="large")
st.html(view.style())
st.html(view.hero())

sources = core.load_fixture()
with st.expander("View original implementation and read-only tests"):
    left, right = st.columns(2)
    left.caption(f"{core.IMPL_FILE} · editable by PatchPilot")
    left.code(sources[core.IMPL_FILE], language="python")
    right.caption(f"{core.TEST_FILE} · read-only")
    right.code(sources[core.TEST_FILE], language="python")


@st.cache_data(ttl=300, show_spinner=False)
def available_models():
    return core.list_models()


# ---- providers and model choice ----
st.html(view.section_heading("Run", "Repair the seeded bug."))
models, model_error = [], None
try:
    models = available_models()
except Exception as e:
    model_error = f"{type(e).__name__}: {str(e)[:200]}"
daytona_key = bool(os.getenv("DAYTONA_API_KEY"))
graph_configured = all(os.getenv(k) for k in GRAPH_KEYS)
st.html(view.provider_chips([
    ("Nosana", "ok" if models else "error",
     f"{len(models)} chat model(s) served" if models else "No chat model available"),
    ("Daytona", "ok" if daytona_key else "error",
     "API key configured" if daytona_key else "DAYTONA_API_KEY missing"),
    ("Neo4j", "ok" if graph_configured else "idle",
     "Graph context configured" if graph_configured else "Optional · not configured"),
]))
if model_error:
    st.error(f"Nosana model list failed: {model_error}")
elif not models:
    st.warning("No Nosana model available, so a repair cannot run.")

model = None
if models:
    preferred = os.getenv("NOSANA_MODEL")
    model = st.selectbox("Nosana model", models, width=420,
                         index=models.index(preferred) if preferred in models else 0)

with st.container(horizontal=True, gap="small"):
    repair = st.button("Repair demo bug", type="primary", disabled=model is None)
    if st.button("Refresh models"):
        available_models.clear()
        st.rerun()

# ---- run ----
if repair:
    # Replace the latest run; one attempt, no retry loop.
    with st.status("Starting a fresh Daytona sandbox…", expanded=True) as status:
        stages = []
        tracker = st.empty()
        tracker.html(view.stage_tracker(stages))

        def on_event(stage, message):
            if stage in PROGRESS:
                stages.append(stage)
                status.update(label=PROGRESS[stage])
                tracker.html(view.stage_tracker(stages))
            st.text(f"{stage} · {message}")

        run = st.session_state["run"] = core.run_repair(model, on_event=on_event)
        status.update(label=f"Run finished: {run.verdict}",
                      state="error" if run.verdict == core.ERROR else "complete", expanded=False)

# ---- evidence ----
run = st.session_state.get("run")
if not run:
    st.html(view.empty_state())
else:
    st.html(view.verdict_banner(run))
    if run.error:
        st.error(run.error)
    if (run.cleanup or "").startswith("CLEANUP FAILED"):
        st.warning(run.cleanup)
    st.html(view.stage_tracker([stage for _, stage, _ in run.events], run.verdict, run.graph_status))

    if run.graph_status != "not used":
        st.html(view.section_heading("Neo4j graph context", "Failure to code."))
        with st.container(key="pp-graph"):
            st.html(view.panel_label("Status", view.chip(view.graph_summary(run.graph_status))))
            st.text(run.graph_status)
            if run.graph_query:
                st.html(view.panel_label("Cypher query"))
                st.code(run.graph_query, language="sql")
                if run.graph_rows:
                    st.table(run.graph_rows)
                else:
                    st.html(view.muted("The query returned no rows."))

    if run.raw_model_output:
        st.html(view.section_heading("Nosana proposal", "Diagnosis and edit."))
        with st.container(key="pp-proposal"):
            if run.diagnosis:
                st.html(view.panel_label("Diagnosis"))
                st.text(run.diagnosis)
                st.html(view.panel_label("Explanation"))
                st.text(run.explanation)
            if run.diff:
                st.html(view.panel_label("Unified diff", view.chip(f"{core.IMPL_FILE} only")))
                st.code(run.diff, language="diff")
            else:
                st.html(view.muted("No patch was applied."))

    st.html(view.section_heading("Daytona evidence", "Before and after."))
    before, after = st.columns(2, gap="medium")
    for column, key, label, code, output in (
            (before, "pp-before", "Before repair", run.baseline_exit, run.baseline_output),
            (after, "pp-after", "After repair · same tests", run.rerun_exit, run.rerun_output)):
        with column, st.container(key=key):
            st.html(view.panel_label(label, view.exit_chip(code) if code is not None else ""))
            if code is None:
                st.html(view.muted("Not run."))
            else:
                st.code(run.test_command, language="bash")
                st.code(output or "(no output)", language="text", height=360)

    with st.expander("Run evidence and event log"):
        st.table([{"time": t, "stage": s, "event": m} for t, s, m in run.events])
        if run.raw_model_output:
            st.html(view.panel_label("Raw model response"))
            st.code(run.raw_model_output, language="json")
    st.download_button("Download run evidence", data=json.dumps(view.run_evidence(run), indent=2),
                       file_name=f"patchpilot-{run.run_id}.json", mime="application/json")
st.caption("VERIFIED means the designated tests passed after the patch; it does not prove the code is "
           "bug-free. The local fixture file is never modified, so each run starts from the original bug.")
