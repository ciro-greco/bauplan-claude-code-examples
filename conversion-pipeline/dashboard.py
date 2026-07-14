"""
Q4 Re-engagement — Session → Purchase Conversion by Customer Value Segment.

Pre-publish PREVIEW: reads `bauplan.segment_conversion` directly off the open
review branch `ciro.q4-reengagement`, so the marketing team sees the numbers
before the data engineer merges the PR to `main`.
"""
import bauplan
import pandas as pd
import plotly.express as px
import streamlit as st

BRANCH = "ciro.q4-reengagement"
TABLE = "bauplan.segment_conversion"
SEGMENT_ORDER = ["high", "medium", "low"]
SEGMENT_COLORS = {"high": "#2563eb", "medium": "#60a5fa", "low": "#cbd5e1"}

st.set_page_config(
    page_title="Q4 Re-engagement — Conversion by Segment",
    page_icon="🎯",
    layout="wide",
)


@st.cache_data(ttl=300)
def load_data():
    """Load the conversion table from the open Bauplan branch."""
    client = bauplan.Client()
    query = f"""
        SELECT
            customer_segment,
            total_sessions,
            converted_sessions,
            conversion_rate,
            purchase_events,
            unique_users
        FROM {TABLE}
    """
    df = client.query(query, ref=BRANCH).to_pandas()

    # Coerce explicitly — Arrow/Iceberg can hand back Decimal / nullable ints.
    for col in [
        "total_sessions",
        "converted_sessions",
        "purchase_events",
        "unique_users",
    ]:
        df[col] = df[col].astype("int64")
    df["conversion_rate"] = df["conversion_rate"].astype("float64")
    df["customer_segment"] = df["customer_segment"].astype("str")

    df["__ord"] = df["customer_segment"].map(
        {s: i for i, s in enumerate(SEGMENT_ORDER)}
    )
    df = df.sort_values("__ord").drop(columns="__ord").reset_index(drop=True)
    return df


df = load_data()

st.title("🎯 Q4 Re-engagement — Conversion by Customer Value Segment")
st.caption(
    f"Session → purchase conversion for this week's activity · "
    f"source `{TABLE}` on branch `{BRANCH}` (pre-publish preview)"
)

# --- Headline KPIs ---
total_sessions = int(df["total_sessions"].sum())
total_converted = int(df["converted_sessions"].sum())
total_purchases = int(df["purchase_events"].sum())
overall_rate = total_converted / total_sessions if total_sessions else 0.0

# Which segment converts best — the actual ad-spend takeaway.
best = df.loc[df["conversion_rate"].idxmax()]

with st.container(horizontal=True):
    st.metric("Total sessions", f"{total_sessions:,}", border=True)
    st.metric("Converted sessions", f"{total_converted:,}", border=True)
    st.metric("Overall conversion", f"{overall_rate:.2%}", border=True)
    st.metric(
        "Best segment",
        best["customer_segment"].title(),
        f"{best['conversion_rate']:.2%}",
        border=True,
    )

# --- Bar chart: conversion rate by segment ---
col_chart, col_table = st.columns([3, 2])

with col_chart:
    with st.container(border=True):
        st.subheader("Conversion rate by segment")
        plot_df = df.copy()
        plot_df["conversion_pct"] = plot_df["conversion_rate"] * 100
        plot_df["label"] = plot_df["customer_segment"].str.title()
        fig = px.bar(
            plot_df,
            x="label",
            y="conversion_pct",
            color="customer_segment",
            color_discrete_map=SEGMENT_COLORS,
            category_orders={"label": [s.title() for s in SEGMENT_ORDER]},
            text=plot_df["conversion_pct"].map(lambda v: f"{v:.2f}%"),
        )
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(
            showlegend=False,
            xaxis_title=None,
            yaxis_title="Conversion rate (%)",
            margin=dict(t=10, b=10, l=10, r=10),
            height=380,
        )
        st.plotly_chart(fig, width='stretch')

with col_table:
    with st.container(border=True):
        st.subheader("Per-segment detail")
        table_df = df.assign(
            Segment=df["customer_segment"].str.title(),
            **{
                "Total sessions": df["total_sessions"],
                "Converted": df["converted_sessions"],
                "Conversion": (df["conversion_rate"] * 100).map(lambda v: f"{v:.2f}%"),
                "Unique users": df["unique_users"],
            },
        )[["Segment", "Total sessions", "Converted", "Conversion", "Unique users"]]
        st.dataframe(table_df, hide_index=True, width='stretch')
        st.caption(
            "A session converts if it contains at least one purchase event. "
            "Segments come from `bauplan.ecommerce_users`."
        )
