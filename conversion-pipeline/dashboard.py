"""
Session -> Purchase Conversion by Customer Value Segment
========================================================

Pre-publish preview for the Q4 re-engagement campaign. Reads the
`bauplan.segment_conversion` result table straight off the open Bauplan
branch (before it is merged to `main`), so marketing can eyeball the
numbers while the pipeline PR is still in review.

The branch is read from the BAUPLAN_REF env var (defaults to the branch
this dashboard was launched against).
"""

import os

import bauplan
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BRANCH = os.environ.get("BAUPLAN_REF", "ciro.sessions_week_conv_1783958303")
TABLE = "bauplan.segment_conversion"

# Fixed value-order + a color per segment; the best performer is highlighted.
SEGMENT_ORDER = ["high", "medium", "low"]
BASE_COLOR = "#9AA6B2"
BEST_COLOR = "#2E7D5B"

st.set_page_config(
    page_title="Session → Purchase Conversion by Segment",
    page_icon="🛒",
    layout="wide",
)


@st.cache_data(ttl=120)
def load_data(ref: str) -> pd.DataFrame:
    client = bauplan.Client()
    df = client.query(
        f"""
        SELECT customer_segment, total_sessions, converting_sessions, conversion_rate
        FROM {TABLE}
        """,
        ref=ref,
    ).to_pandas()
    df["customer_segment"] = df["customer_segment"].str.lower()
    df["order"] = df["customer_segment"].map({s: i for i, s in enumerate(SEGMENT_ORDER)})
    return df.sort_values("order").drop(columns="order").reset_index(drop=True)


st.title("🛒 Session → Purchase Conversion by Customer Value Segment")
st.caption(
    f"Q4 re-engagement · this week's shopping activity · live preview off branch "
    f"`{BRANCH}` (not yet published to `main`)"
)

try:
    df = load_data(BRANCH)
    if df.empty:
        st.error("No rows in segment_conversion. Has the pipeline been run on this branch?")
        st.stop()

    total_sessions = int(df["total_sessions"].sum())
    total_converting = int(df["converting_sessions"].sum())
    overall_rate = total_converting / total_sessions if total_sessions else 0.0
    best = df.loc[df["conversion_rate"].idxmax()]

    # --- Headline numbers ---
    with st.container(horizontal=True):
        st.metric("Total sessions", f"{total_sessions:,}", border=True)
        st.metric("Converted sessions", f"{total_converting:,}", border=True)
        st.metric("Overall conversion", f"{overall_rate:.2%}", border=True)
        st.metric(
            "Best segment",
            best["customer_segment"].capitalize(),
            f"{best['conversion_rate']:.2%}",
            border=True,
        )

    st.markdown("---")

    col_chart, col_table = st.columns([2, 1])

    # --- Bar chart: segment x conversion rate ---
    with col_chart:
        with st.container(border=True):
            st.subheader("Conversion rate by segment")
            colors = [
                BEST_COLOR if s == best["customer_segment"] else BASE_COLOR
                for s in df["customer_segment"]
            ]
            fig = go.Figure(
                go.Bar(
                    x=df["customer_segment"].str.capitalize(),
                    y=df["conversion_rate"],
                    marker_color=colors,
                    text=[f"{r:.2%}" for r in df["conversion_rate"]],
                    textposition="outside",
                    customdata=df[["total_sessions", "converting_sessions"]],
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "Conversion: %{y:.2%}<br>"
                        "Sessions: %{customdata[0]:,}<br>"
                        "Converted: %{customdata[1]:,}<extra></extra>"
                    ),
                )
            )
            fig.update_layout(
                yaxis=dict(title="Session → purchase rate", tickformat=".1%"),
                xaxis=dict(title="Customer value segment"),
                margin=dict(t=20, b=10, l=10, r=10),
                height=440,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    # --- Table ---
    with col_table:
        with st.container(border=True):
            st.subheader("The numbers")
            show = df.copy()
            show["conversion_rate"] = (show["conversion_rate"] * 100).map("{:.2f}%".format)
            show["total_sessions"] = show["total_sessions"].map("{:,}".format)
            show["converting_sessions"] = show["converting_sessions"].map("{:,}".format)
            show["customer_segment"] = show["customer_segment"].str.capitalize()
            show.columns = ["Segment", "Sessions", "Converted", "Conv. rate"]
            st.dataframe(show, hide_index=True, use_container_width=True)

    st.markdown(
        f"**Takeaway:** _{best['customer_segment'].capitalize()}_-value shoppers convert best "
        f"at **{best['conversion_rate']:.2%}** — worth weighting Q4 re-engagement spend toward them."
    )

except Exception as exc:  # noqa: BLE001
    st.error(f"Error loading data from Bauplan branch `{BRANCH}`: {exc}")
    st.info("Ensure the pipeline has been run on this branch and the branch still exists.")
