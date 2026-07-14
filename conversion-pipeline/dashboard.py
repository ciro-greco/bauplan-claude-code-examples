"""
Q4 re-engagement — session -> purchase conversion by customer value segment.
Pre-publish preview: reads bauplan.segment_conversion from the open review branch.
"""
import os

import bauplan
import polars as pl
import streamlit as st

BRANCH = os.environ.get("BAUPLAN_BRANCH", "ciro.sessions_week_conv_1784033575")
TABLE = "bauplan.segment_conversion"
SEGMENT_ORDER = ["high", "medium", "low"]

st.set_page_config(page_title="Segment Conversion — Q4 Re-engagement", page_icon="📈", layout="wide")


@st.cache_data(ttl=300)
def load_data(branch: str) -> pl.DataFrame:
    client = bauplan.Client()
    tbl = client.query(
        f"SELECT customer_segment, total_sessions, converted_sessions, conversion_rate "
        f"FROM {TABLE}",
        ref=branch,
    )
    df = pl.from_arrow(tbl)
    order = pl.DataFrame({"customer_segment": SEGMENT_ORDER, "_rank": [0, 1, 2]})
    return df.join(order, on="customer_segment", how="left").sort("_rank").drop("_rank")


st.title("📈 Session → Purchase Conversion by Segment")
st.caption(
    f"This week's shopping activity · pre-publish preview on branch `{BRANCH}` · "
    "supports Q4 re-engagement ad-spend prioritization"
)

df = load_data(BRANCH)

total_sessions = int(df["total_sessions"].sum())
total_converted = int(df["converted_sessions"].sum())
overall_rate = total_converted / total_sessions if total_sessions else 0.0
best = df.sort("conversion_rate", descending=True).row(0, named=True)

# --- Headline KPIs ---
with st.container(horizontal=True):
    st.metric("Overall conversion", f"{overall_rate:.2%}", border=True)
    st.metric("Total sessions", f"{total_sessions:,}", border=True)
    st.metric("Purchases (sessions)", f"{total_converted:,}", border=True)
    st.metric(
        "Best-converting segment",
        best["customer_segment"].capitalize(),
        f"{best['conversion_rate']:.2%}",
        border=True,
    )

# --- Chart + table ---
left, right = st.columns([3, 2])

with left:
    with st.container(border=True):
        st.subheader("Conversion rate by segment")
        chart_df = df.select(
            pl.col("customer_segment").str.to_titlecase().alias("Segment"),
            (pl.col("conversion_rate") * 100).round(2).alias("Conversion rate (%)"),
        ).to_pandas()
        st.bar_chart(chart_df, x="Segment", y="Conversion rate (%)", color="#2563eb")

with right:
    with st.container(border=True):
        st.subheader("Detail")
        table_df = df.select(
            pl.col("customer_segment").str.to_titlecase().alias("Segment"),
            pl.col("total_sessions").alias("Sessions"),
            pl.col("converted_sessions").alias("Converted"),
            (pl.col("conversion_rate") * 100).round(2).alias("Rate %"),
        ).to_pandas()
        st.dataframe(table_df, hide_index=True, use_container_width=True)

st.caption(
    "A session converts if it contains a purchase event. Segments come from "
    "`bauplan.ecommerce_users.customer_segment`, joined on `user_id`."
)
