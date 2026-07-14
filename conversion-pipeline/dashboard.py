"""
Q4 re-engagement — session→purchase conversion by customer value segment.

Pre-publish preview: reads segment_conversion straight off the open Bauplan branch
so marketing can eyeball the numbers before the data engineer merges the PR.

Launch:
  .venv/bin/streamlit run conversion-pipeline/dashboard.py --server.headless true --server.port 8899
"""
import bauplan
import pandas as pd
import streamlit as st

BRANCH = "ciro.q4-reengagement"
TABLE = "bauplan.segment_conversion"
SEGMENT_ORDER = ["high", "medium", "low"]

st.set_page_config(page_title="Q4 Re-engagement — Conversion by Segment", layout="wide")


@st.cache_data(ttl=300)
def load_data(branch: str) -> pd.DataFrame:
    client = bauplan.Client()
    tbl = client.query(f"SELECT * FROM {TABLE}", ref=branch)
    df = tbl.to_pandas()
    df["customer_segment"] = pd.Categorical(
        df["customer_segment"], categories=SEGMENT_ORDER, ordered=True
    )
    return df.sort_values("customer_segment").reset_index(drop=True)


df = load_data(BRANCH)

st.title("Q4 Re-engagement — Session→Purchase Conversion")
st.caption(
    f"Value segment × conversion rate · source `{TABLE}` on branch `{BRANCH}` "
    "(pre-publish preview)"
)

# --- Headline KPI row: conversion rate per segment ---
overall = df["converted_sessions"].sum() / df["total_sessions"].sum()
with st.container(horizontal=True):
    st.metric("Overall conversion", f"{overall * 100:.2f}%", border=True)
    for _, row in df.iterrows():
        seg = row["customer_segment"]
        delta = (row["conversion_rate"] - overall) * 100
        st.metric(
            f"{seg.capitalize()} value",
            f"{row['conversion_rate'] * 100:.2f}%",
            f"{delta:+.2f} pts vs overall",
            border=True,
        )

# --- Charts ---
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("Conversion rate by segment")
        chart_df = df.assign(conversion_pct=(df["conversion_rate"] * 100).round(2))
        st.bar_chart(
            chart_df, x="customer_segment", y="conversion_pct", color="#4C78A8"
        )
        st.caption("Percent of sessions that reached a purchase.")

with col2:
    with st.container(border=True):
        st.subheader("Session volume by segment")
        st.bar_chart(df, x="customer_segment", y="total_sessions", color="#72B7B2")
        st.caption("Total sessions this week — the denominator behind each rate.")

# --- Detail table ---
with st.container(border=True):
    st.subheader("Segment detail")
    show = df.copy()
    show["conversion_rate"] = (show["conversion_rate"] * 100).round(2)
    st.dataframe(
        show.rename(
            columns={
                "customer_segment": "Segment",
                "total_sessions": "Total sessions",
                "converted_sessions": "Converted sessions",
                "conversion_rate": "Conversion rate (%)",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

best = df.loc[df["conversion_rate"].idxmax(), "customer_segment"]
st.info(
    f"**{best.capitalize()}-value** sessions convert best — prioritize ad spend there "
    "for the Q4 re-engagement push."
)
