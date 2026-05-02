"""Page 4: Pipeline status + run history."""
import time

import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(page_title="Pipeline Status", layout="wide")
st.title("⚙️ Pipeline Status")

# Auto-refresh toggle
auto_refresh = st.toggle("Auto-refresh every 10s", value=False)

run_id = st.text_input("Run ID", value=st.session_state.get("active_run_id", ""))

col_refresh, col_clear = st.columns([1, 5])
if col_refresh.button("🔄 Refresh Now") or auto_refresh:
    pass  # will fetch below

if run_id:
    try:
        resp = requests.get(f"{API}/status/{run_id}", timeout=10)
        resp.raise_for_status()
        s = resp.json()
    except Exception as exc:
        st.error(f"Could not fetch status: {exc}")
        st.stop()

    st.markdown("---")

    # Error banner
    run_status = s.get("status", "")
    if run_status.startswith("failed"):
        reason = run_status.replace("failed:", "").replace("_", " ")
        st.error(f"### ❌ Run Failed — {reason}")
        if s.get("error"):
            with st.expander("Show error details", expanded=True):
                st.code(s["error"], language="text")

    # Summary row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", run_status or "—")
    c2.metric("Score", f"{float(s.get('score') or 0):.2f} / 10")
    c3.metric("Iteration", int(s.get("iteration") or 0))
    c4.metric("Pipeline Run ID", s.get("pipeline_run_id") or "—")

    # Pipeline state
    pipeline_run_id = s.get("pipeline_run_id", "")
    if pipeline_run_id:
        st.subheader("Pipeline Run Details")
        pipeline_status = s.get("pipeline_status") or {}
        state = pipeline_status.get("state", "UNKNOWN")
        done = pipeline_status.get("done", False)
        success = pipeline_status.get("success", False)
        msg = pipeline_status.get("message", "")

        if done and success:
            st.success(f"Pipeline **{pipeline_run_id}** completed successfully.")
        elif done and not success:
            st.error(f"Pipeline **{pipeline_run_id}** failed: {msg}")
        else:
            st.info(f"Pipeline **{pipeline_run_id}** is **{state}**. {msg}")
            st.progress(0.5 if state == "RUNNING" else 0.1)

    # Error display
    if s.get("error"):
        st.error(f"Error: {s['error']}")

    # Iteration history from metric_results
    if s.get("metric_results"):
        st.subheader(f"Metrics — Iteration {s.get('iteration', 0)}")
        cats = s["metric_results"].get("categories", {})
        if cats:
            rows = [
                {"Category": k, "Score": f"{v['score']:.2f}", "Passed": "✅" if v["passed"] else "❌"}
                for k, v in cats.items()
            ]
            st.table(rows)

    if auto_refresh:
        time.sleep(10)
        st.rerun()

# ------------------------------------------------------------------
# All runs list
# ------------------------------------------------------------------
st.markdown("---")
st.subheader("All Runs")
if st.button("Load All Runs"):
    try:
        resp = requests.get(f"{API}/runs", timeout=10)
        resp.raise_for_status()
        runs = resp.json().get("runs", [])
        if runs:
            for r in runs:
                try:
                    rs = requests.get(f"{API}/status/{r}", timeout=5).json()
                    st.markdown(
                        f"- `{r}` — **{rs.get('status','?')}** — score: {rs.get('score', 0):.2f}"
                    )
                except Exception:
                    st.markdown(f"- `{r}`")
        else:
            st.info("No runs found.")
    except Exception as exc:
        st.error(f"Could not load runs: {exc}")
