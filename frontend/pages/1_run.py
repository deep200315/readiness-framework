"""Page 1: Table selector + preview + start a new quality run."""
import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(page_title="New Run", layout="wide")
st.title("🚀 Start a New Data Quality Run")

# ------------------------------------------------------------------
# Step 1: Table selector
# ------------------------------------------------------------------
st.subheader("1. Select Source Table")

if st.button("🔄 Refresh Table List"):
    st.session_state.pop("tables", None)
    st.session_state.pop("preview", None)

if "tables" not in st.session_state:
    with st.spinner("Fetching tables from Databricks…"):
        try:
            resp = requests.get(f"{API}/tables", timeout=60)
            resp.raise_for_status()
            st.session_state["tables"] = resp.json()["tables"]
        except Exception as exc:
            st.error(f"Could not fetch tables: {exc}")
            st.session_state["tables"] = []

tables = st.session_state.get("tables", [])

if tables:
    filter_text = st.text_input("Filter tables", placeholder="type to filter…")
    filtered = [t for t in tables if filter_text.lower() in t.lower()] if filter_text else tables
    selected_table = st.selectbox("Available Tables", filtered)
else:
    selected_table = st.text_input(
        "Table reference (catalog.schema.table)",
        placeholder="datareadiness.default.my_table",
    )

# ------------------------------------------------------------------
# Step 2: Preview table + auto-suggest usecase
# ------------------------------------------------------------------
if selected_table:
    st.subheader("2. Preview Table")

    preview_key = f"preview_{selected_table}"
    if st.button("👁 Load Preview & Suggest Usecase") or preview_key not in st.session_state:
        parts = selected_table.split(".")
        if len(parts) == 3:
            with st.spinner("Fetching sample data and generating usecase suggestion…"):
                try:
                    catalog, schema, table = parts
                    resp = requests.get(f"{API}/preview/{catalog}/{schema}/{table}", timeout=60)
                    resp.raise_for_status()
                    st.session_state[preview_key] = resp.json()
                except Exception as exc:
                    st.warning(f"Could not load preview: {exc}")
                    st.session_state[preview_key] = None

    preview = st.session_state.get(preview_key)
    if preview:
        # Schema
        with st.expander("📋 Table Schema", expanded=False):
            st.table(preview.get("schema", []))

        # Sample rows
        with st.expander("🔍 Sample Data (5 rows)", expanded=True):
            sample = preview.get("sample_rows", [])
            if sample:
                st.dataframe(sample, width="stretch")
            else:
                st.info("No rows returned.")

        # Write directly to the widget key so Streamlit picks it up on next render
        suggested = preview.get("suggested_usecase", "")
        if suggested:
            st.session_state["usecase_input"] = suggested

# ------------------------------------------------------------------
# Step 3: Usecase description
# ------------------------------------------------------------------
st.subheader("3. Describe the Usecase")
st.caption("GPT-4o auto-suggested this based on your table schema and sample data. Edit if needed.")

usecase = st.text_area(
    "What is this data used for?",
    height=100,
    key="usecase_input",
)

# ------------------------------------------------------------------
# Step 4: Launch
# ------------------------------------------------------------------
st.subheader("4. Run Data Quality Check")
if st.button("▶ Start Run", type="primary", disabled=not selected_table):
    if not usecase.strip():
        st.warning("Please describe the usecase (or load a preview to auto-generate one).")
    else:
        with st.spinner("Launching agent…"):
            try:
                resp = requests.post(
                    f"{API}/run-checks",
                    json={"source_table": selected_table, "usecase": usecase},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                run_id = data["run_id"]
                st.session_state["active_run_id"] = run_id
                st.session_state.pop("usecase_input", None)  # reset for next run
                st.success(f"Run started! **run_id:** `{run_id}`")
                st.info("Go to 📊 Dashboard or ✅ Approvals to monitor progress.")
            except Exception as exc:
                st.error(f"Failed to start run: {exc}")

# ------------------------------------------------------------------
# Active run summary
# ------------------------------------------------------------------
if "active_run_id" in st.session_state:
    run_id = st.session_state["active_run_id"]
    st.markdown("---")
    st.subheader(f"Active Run: `{run_id}`")
    try:
        resp = requests.get(f"{API}/status/{run_id}", timeout=10)
        if resp.ok:
            s = resp.json()
            run_status = s.get("status", "—")
            col1, col2, col3 = st.columns(3)
            col1.metric("Status", run_status)
            col2.metric("Score", f"{float(s.get('score') or 0):.2f} / 10")
            col3.metric("Iteration", int(s.get("iteration") or 0))
            if run_status.startswith("failed"):
                reason = run_status.replace("failed:", "").replace("_", " ")
                st.error(f"❌ Run failed — {reason}")
                if s.get("error"):
                    with st.expander("Error details"):
                        st.code(s["error"], language="text")
    except Exception:
        pass
    if st.button("⏹ Clear Active Run"):
        del st.session_state["active_run_id"]
        st.rerun()
