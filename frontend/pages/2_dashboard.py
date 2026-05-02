"""Page 2: Metric scores dashboard."""
import plotly.graph_objects as go
import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(page_title="Dashboard", layout="wide")
st.title("📊 Metric Results Dashboard")

run_id = st.text_input("Run ID", value=st.session_state.get("active_run_id", ""))
col_refresh, _ = st.columns([1, 8])
col_refresh.button("🔄 Refresh")

if not run_id:
    st.info("Enter a run ID above or start a run from the **New Run** page.")
    st.stop()

try:
    resp = requests.get(f"{API}/status/{run_id}", timeout=10)
    resp.raise_for_status()
    s = resp.json()
except Exception as exc:
    st.error(f"Could not fetch status: {exc}")
    st.stop()

status = s.get("status", "unknown")

# ------------------------------------------------------------------
# Error banner — shown prominently at the top whenever a run fails
# ------------------------------------------------------------------
if status.startswith("failed"):
    reason = status.replace("failed:", "").replace("_", " ")
    st.error(f"### ❌ Run Failed — {reason}")
    if s.get("error"):
        with st.expander("Show error details", expanded=True):
            st.code(s["error"], language="text")
    st.markdown("---")

# ------------------------------------------------------------------
# Top metrics row
# ------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
score = float(s.get("score") or 0)
iteration = int(s.get("iteration") or 0)

col1.metric("Overall Score", f"{score:.2f} / 10")
col2.metric("Status", status)
col3.metric("Iteration", iteration)
col4.metric("Verdict", "✅ PASS" if score >= 8.0 else "❌ FAIL")

if status == "running":
    st.info("⏳ Agent is running — refresh to see updated results.")

st.markdown("---")

# ------------------------------------------------------------------
# Category breakdown
# ------------------------------------------------------------------
metric_results = s.get("metric_results") or {}
categories = metric_results.get("categories", {})

if categories:
    st.subheader("Category Scores")
    cat_cols = st.columns(len(categories))
    for idx, (cat, data) in enumerate(categories.items()):
        cat_score = data.get("score", 0)
        cat_pass = data.get("passed", False)
        cat_cols[idx].metric(
            cat.capitalize(),
            f"{cat_score:.2f}",
            delta="✅" if cat_pass else "❌",
            delta_color="normal" if cat_pass else "inverse",
        )

    # Radar chart
    labels = [c.capitalize() for c in categories.keys()]
    values = [categories[c]["score"] for c in categories]
    fig = go.Figure(go.Scatterpolar(
        r=values + [values[0]],
        theta=labels + [labels[0]],
        fill="toself",
        line_color="#1f77b4",
        fillcolor="rgba(31,119,180,0.2)",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
        showlegend=False,
        height=400,
    )
    st.plotly_chart(fig, width="stretch")

    # Per-category failures
    st.subheader("Failures by Category")
    for cat, data in categories.items():
        failures = data.get("failures", [])
        if failures:
            with st.expander(f"❌ {cat.capitalize()} — {len(failures)} failure(s)", expanded=True):
                for f in failures:
                    st.markdown(f"- {f}")
        else:
            st.success(f"✅ {cat.capitalize()}: no failures")

    # Detailed check table
    st.subheader("Detailed Checks")
    rows = []
    for cat, data in categories.items():
        for check in data.get("checks", []):
            rows.append({
                "Category": cat,
                "Check": check["name"],
                "Passed": "✅" if check["passed"] else "❌",
                "Score": f"{check['score']:.2f}",
                "Value": str(check.get("value", "")),
                "Threshold": str(check.get("threshold", "")),
                "Detail": str(check.get("detail", "")),
            })
    if rows:
        st.dataframe(rows, width="stretch")
else:
    if not status.startswith("failed"):
        st.info("Metrics not yet available — run is still in progress.")
