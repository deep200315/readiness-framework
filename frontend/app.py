"""Streamlit multi-page app entry point."""
import streamlit as st

st.set_page_config(
    page_title="Data Readiness Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("Data Readiness Agent")
st.sidebar.markdown("AI-driven data quality with human-in-the-loop approvals.")
st.sidebar.markdown("---")
st.sidebar.markdown("**Navigation**")
st.sidebar.page_link("pages/1_run.py", label="▶ New Run", icon="🚀")
st.sidebar.page_link("pages/2_dashboard.py", label="📊 Dashboard", icon="📊")
st.sidebar.page_link("pages/3_approvals.py", label="✅ Approvals", icon="✅")
st.sidebar.page_link("pages/4_pipeline_status.py", label="⚙ Pipeline Status", icon="⚙️")

st.title("Data Readiness Agent")
st.markdown("""
Welcome! Use the sidebar to:
1. **New Run** — Select a Databricks table and start a data quality run
2. **Dashboard** — View metric scores and category breakdowns
3. **Approvals** — Approve or reject AI-suggested fixes
4. **Pipeline Status** — Monitor active pipeline runs
""")
