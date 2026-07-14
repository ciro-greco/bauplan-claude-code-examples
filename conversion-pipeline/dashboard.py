"""
Q4 Re-engagement — session→purchase conversion by customer value segment.

Pre-publish preview: reads bauplan.conversion_by_segment from the OPEN review
branch (not main) so the marketing team can see the numbers before the pipeline
is merged.

    .venv/bin/streamlit run conversion-pipeline/dashboard.py \
        --server.headless true --server.port 8899
"""
import bauplan
import pandas as pd
import streamlit as st

BRANCH = "ciro.q4-reengagement"
TABLE = "bauplan.conversion_by_segment"
SEGMENT_ORDER = ["high", "medium", "low"]

st.set_page_config(page_title="Q4 Re-engagement — Conversion by Segment", layout="wide")


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    client = bauplan.Client()
    tbl = client.query(
        f"SELECT customer_segment, total_sessions, converting_sessions, conversion_rate "
        f"FROM {TABLE}",
        ref=BRANCH,
    )
    df = tbl.to_pandas()
    # Coerce explicitly — query engines can hand back Decimal / object dtypes.
    df["total_sessions"] = df["total_sessions"].astype("int64")
    df["converting_sessions"] = df["converting_sessions"].astype("int64")
    df["conversion_rate"] = df["conversion_rate"].astype("float64")
    df["customer_segment"] = df["customer_segment"].astype("str")
    df["__order"] = df["customer_segment"].map(
        {s: i for i, s in enumerate(SEGMENT_ORDER)}
    ).fillna(99)
    return df.sort_values("__order").drop(columns="__order").reset_index(drop=True)


df = load_data()

total_sessions = int(df["total_sessions"].sum())
total_conversions = int(df["converting_sessions"].sum())
overall_rate = total_conversions / total_sessions if total_sessions else 0.0

st.title("Q4 Re-engagement — Session→Purchase Conversion")
st.caption(
    f"Pre-publish preview from open branch `{BRANCH}` · source `{TABLE}` · "
    "this week's sessions"
)

# --- Headline KPIs ---
with st.container(horizontal=True):
    st.metric("Total sessions", f"{total_sessions:,}", border=True)
    st.metric("Converting sessions", f"{total_conversions:,}", border=True)
    st.metric("Overall conversion", f"{overall_rate:.2%}", border=True)

# --- Chart + table ---
col1, col2 = st.columns([3, 2])

with col1:
    with st.container(border=True):
        st.subheader("Conversion rate by value segment")
        chart_df = df.assign(conversion_pct=df["conversion_rate"] * 100).set_index(
            "customer_segment"
        )
        st.bar_chart(
            chart_df,
            y="conversion_pct",
            color="#4C78A8",
            height=360,
        )
        st.caption("Bars show session→purchase conversion rate (%) per segment.")

with col2:
    with st.container(border=True):
        st.subheader("By the numbers")
        display = df.copy()
        display["conversion_rate"] = (display["conversion_rate"] * 100).map(
            lambda v: f"{v:.2f}%"
        )
        display["total_sessions"] = display["total_sessions"].map("{:,}".format)
        display["converting_sessions"] = display["converting_sessions"].map(
            "{:,}".format
        )
        display = display.rename(
            columns={
                "customer_segment": "Segment",
                "total_sessions": "Sessions",
                "converting_sessions": "Conversions",
                "conversion_rate": "Conv. rate",
            }
        )
        st.dataframe(display, hide_index=True, use_container_width=True)

        best = df.loc[df["conversion_rate"].idxmax(), "customer_segment"]
        st.markdown(
            f"**Highest-converting segment: `{best}`** — prioritise ad spend here."
        )
