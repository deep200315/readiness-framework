"""Page 3: Human-in-the-loop approvals."""
import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(page_title="Approvals", layout="wide")
st.title("✅ Human Approvals")

run_id = st.text_input("Run ID", value=st.session_state.get("active_run_id", ""))

if not run_id:
    st.info("Enter a run ID above.")
    st.stop()

try:
    resp = requests.get(f"{API}/status/{run_id}", timeout=10)
    resp.raise_for_status()
    s = resp.json()
except Exception as exc:
    st.error(f"Could not fetch status: {exc}")
    st.stop()

status = s.get("status") or ""
score = float(s.get("score") or 0)
iteration = int(s.get("iteration") or 0)

# Error banner
if status.startswith("failed"):
    reason = status.replace("failed:", "").replace("_", " ")
    st.error(f"### ❌ Run Failed — {reason}")
    if s.get("error"):
        with st.expander("Show error details", expanded=True):
            st.code(s["error"], language="text")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Current Score", f"{score:.2f} / 10")
col2.metric("Iteration", iteration)
col3.metric("Status", status)
st.markdown("---")


def _post_decision(decision: str, checkpoint: str):
    try:
        resp = requests.post(
            f"{API}/approve-step",
            json={"run_id": run_id, "decision": decision, "checkpoint": checkpoint},
            timeout=15,
        )
        resp.raise_for_status()
        st.success(f"Decision '{decision}' submitted for checkpoint '{checkpoint}'.")
        st.rerun()
    except Exception as exc:
        st.error(f"Failed to submit decision: {exc}")


# ------------------------------------------------------------------
# Checkpoint 1: Approve suggestions
# ------------------------------------------------------------------
if status == "awaiting_approval_suggestions":
    st.subheader("🤖 AI-Generated Fix Suggestions")
    st.markdown(f"**Overall Score:** {score:.2f}/10 — below threshold (8.0). Review the suggestions below.")

    suggestions = s.get("suggestions", [])
    if not suggestions:
        st.warning("No suggestions available yet.")
    else:
        for i, fix in enumerate(suggestions):
            with st.expander(f"Fix {i+1}: {fix.get('description', 'No description')}", expanded=True):
                col1, col2 = st.columns([2, 1])
                col1.markdown(f"**Category:** {fix.get('type', '—')}")
                col1.markdown(f"**Transform:** `{fix.get('transform_fn_name', 'N/A')}`")
                col1.markdown(f"**Params:** `{fix.get('params', {})}`")
                col2.metric(
                    "Expected Improvement",
                    f"+{fix.get('expected_score_improvement', 0):.2f} pts",
                )

    st.markdown("---")
    col_approve, col_reject = st.columns(2)
    if col_approve.button("✅ Approve & Apply Fixes", type="primary"):
        _post_decision("approved", "suggestions")
    if col_reject.button("❌ Reject & Abort Run", type="secondary"):
        _post_decision("rejected", "suggestions")

# ------------------------------------------------------------------
# Checkpoint 2: Approve pipeline result
# ------------------------------------------------------------------
elif status == "awaiting_approval_pipeline":
    st.subheader("⚙️ Pipeline Complete — Review Cleaned Data")
    st.markdown("The ML pipeline has applied the approved transformations. Review and approve before re-running metrics.")

    pipeline_run_id = s.get("pipeline_run_id", "")
    if pipeline_run_id:
        st.info(f"Pipeline run ID: `{pipeline_run_id}`")

    st.markdown("---")
    col_approve, col_reject = st.columns(2)
    if col_approve.button("✅ Approve — Re-run Metrics", type="primary"):
        _post_decision("approved", "pipeline_result")
    if col_reject.button("❌ Reject & Abort Run", type="secondary"):
        _post_decision("rejected", "pipeline_result")

elif status == "running":
    st.info("⏳ Agent is running. No action required yet.")
    st.markdown("Refresh this page to check for pending approvals.")
    if st.button("🔄 Refresh"):
        st.rerun()

elif status == "done":
    st.success("🎉 Run complete! Data passed quality checks and was pushed to the target table.")

elif status and status.startswith("failed"):
    st.error(f"Run ended: `{status}`")
    if s.get("error"):
        st.code(s["error"])

else:
    st.info(f"Current status: `{status}` — no action required.")
