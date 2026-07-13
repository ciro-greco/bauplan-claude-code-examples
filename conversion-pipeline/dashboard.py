"""
Session -> Purchase Conversion by Customer Segment
==================================================

Pre-publish preview for the Q4 re-engagement campaign. Reads the `segment_conversion`
table straight off the open Bauplan branch (not yet merged to main), so marketing can
review the numbers before they are published.

Run headless:
    BAUPLAN_REF=<branch> .venv/bin/streamlit run conversion-pipeline/dashboard.py \
        --server.headless true --server.port 8899
"""

import os

import bauplan
import plotly.graph_objects as go
import streamlit as st

# The open branch we built everything on. Overridable via env var.
DEFAULT_REF = "ciro.sessions_week_conv_1783878779"
BAUPLAN_REF = os.environ.get("BAUPLAN_REF", DEFAULT_REF)

# Value-segment order (high value -> low value) and a colour per segment.
SEGMENT_ORDER = ["high", "medium", "low"]
SEGMENT_COLORS = {"high": "#2563eb", "medium": "#7c9cf0", "low": "#c7d3f5"}

st.set_page_config(
    page_title="Session → Purchase Conversion by Segment",
    page_icon="🛒",
    layout="wide",
)


@st.cache_data(ttl=300)
def load_data(ref: str):
    """Load segment_conversion from the given Bauplan ref (branch)."""
    client = bauplan.Client()
    query = """
        SELECT
            customer_segment,
            total_sessions,
            CAST(converting_sessions AS BIGINT) AS converting_sessions,
            conversion_rate
        FROM bauplan.segment_conversion
    """
    tbl = client.query(query, ref=ref)
    df = tbl.to_pandas()
    # Enforce the high -> medium -> low ordering.
    df["__order"] = df["customer_segment"].map({s: i for i, s in enumerate(SEGMENT_ORDER)})
    df = df.sort_values("__order").drop(columns="__order").reset_index(drop=True)
    return df


# ---------------------------------------------------------------- header
st.title("🛒 Session → Purchase Conversion by Customer Segment")
st.caption(
    "This week's shopping activity · pre-publish preview from Bauplan branch "
    f"`{BAUPLAN_REF}` (not yet merged to `main`)"
)

try:
    df = load_data(BAUPLAN_REF)
except Exception as exc:  # surface connection/query problems inside the app
    st.error(f"Could not load data from Bauplan ref `{BAUPLAN_REF}`:\n\n{exc}")
    st.stop()

if df.empty:
    st.warning("No rows in bauplan.segment_conversion on this branch.")
    st.stop()

# ---------------------------------------------------------------- KPIs
total_sessions = int(df["total_sessions"].sum())
total_converting = int(df["converting_sessions"].sum())
overall_rate = total_converting / total_sessions if total_sessions else 0.0

best = df.loc[df["conversion_rate"].idxmax()]
worst = df.loc[df["conversion_rate"].idxmin()]

with st.container(horizontal=True):
    st.metric("Total sessions", f"{total_sessions:,}", border=True)
    st.metric("Converting sessions", f"{total_converting:,}", border=True)
    st.metric("Overall conversion", f"{overall_rate * 100:.2f}%", border=True)
    st.metric(
        "Best segment",
        best["customer_segment"].capitalize(),
        f"{best['conversion_rate'] * 100:.2f}%",
        border=True,
    )

# ---------------------------------------------------------------- chart + table
left, right = st.columns([3, 2])

with left:
    with st.container(border=True):
        st.subheader("Conversion rate by segment")
        pct = (df["conversion_rate"] * 100).round(2)
        fig = go.Figure(
            go.Bar(
                x=df["customer_segment"].str.capitalize(),
                y=pct,
                marker_color=[SEGMENT_COLORS[s] for s in df["customer_segment"]],
                text=[f"{v:.2f}%" for v in pct],
                textposition="outside",
                cliponaxis=False,
            )
        )
        fig.update_layout(
            yaxis_title="Conversion rate (%)",
            xaxis_title="Customer value segment",
            margin=dict(l=10, r=10, t=10, b=10),
            height=380,
            yaxis=dict(range=[0, pct.max() * 1.25]),
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    with st.container(border=True):
        st.subheader("Detail")
        table = df.copy()
        table["conversion_rate"] = (table["conversion_rate"] * 100).round(2)
        table.columns = ["Segment", "Total sessions", "Converting", "Conversion %"]
        table["Segment"] = table["Segment"].str.capitalize()
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Total sessions": st.column_config.NumberColumn(format="%,d"),
                "Converting": st.column_config.NumberColumn(format="%,d"),
                "Conversion %": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )

# ---------------------------------------------------------------- takeaway
st.container(border=True).markdown(
    f"**Takeaway:** *{best['customer_segment'].capitalize()}*-value shoppers convert "
    f"best at **{best['conversion_rate'] * 100:.2f}%**, vs "
    f"**{worst['conversion_rate'] * 100:.2f}%** for *{worst['customer_segment']}*-value — "
    "prioritise ad spend accordingly."
)
