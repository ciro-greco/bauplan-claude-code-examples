"""
Q4 re-engagement — session -> purchase conversion by customer value segment.

Reads the pipeline output table `bauplan.segment_conversion` straight off the
OPEN Bauplan branch (pre-publish preview) via the SDK, so marketing can see the
numbers before the data engineer merges the review PR.

Run:
    .venv/bin/streamlit run conversion-pipeline/dashboard.py \
        --server.headless true --server.port 8899
"""
import altair as alt
import bauplan
import pandas as pd
import streamlit as st

BRANCH = "ciro.q4-reengagement-0716"
TABLE = "bauplan.segment_conversion"
SEGMENT_ORDER = ["high", "medium", "low"]
ACCENT = "#4C6EF5"
MUTED = "#C4C9D4"


@st.cache_data(ttl=300)
def load_segments(branch: str = BRANCH) -> pd.DataFrame:
    """Load segment_conversion from the open branch, with explicit dtypes.

    conversions comes back as decimal from the warehouse — coerce everything to
    plain numeric so downstream math and Altair never choke on Decimal/None.
    """
    client = bauplan.Client()
    tbl = client.query(
        f"SELECT customer_segment, sessions, conversions, conversion_rate "
        f"FROM {TABLE}",
        ref=branch,
    )
    df = tbl.to_pandas()
    df["customer_segment"] = df["customer_segment"].astype(str)
    df["sessions"] = df["sessions"].astype("int64")
    df["conversions"] = df["conversions"].astype("float").astype("int64")
    df["conversion_rate"] = df["conversion_rate"].astype("float")
    df["order"] = df["customer_segment"].map(
        {s: i for i, s in enumerate(SEGMENT_ORDER)}
    )
    return df.sort_values("order").reset_index(drop=True)


def main() -> None:
    st.set_page_config(
        page_title="Q4 Re-engagement · Conversion by Segment",
        page_icon="📊",
        layout="wide",
    )

    df = load_segments()

    total_sessions = int(df["sessions"].sum())
    total_conversions = int(df["conversions"].sum())
    overall_rate = total_conversions / total_sessions if total_sessions else 0.0
    best = df.loc[df["conversion_rate"].idxmax()]

    st.title("Q4 Re-engagement — Session → Purchase Conversion")
    st.caption(
        f"This week's shopping activity by customer value segment · "
        f"live off branch `{BRANCH}` (pre-publish preview)"
    )

    # --- Headline KPIs ---
    with st.container(horizontal=True):
        st.metric("Sessions", f"{total_sessions:,}", border=True)
        st.metric("Purchases", f"{total_conversions:,}", border=True)
        st.metric("Overall conversion", f"{overall_rate:.2%}", border=True)
        st.metric(
            "Top segment",
            best["customer_segment"].capitalize(),
            f"{best['conversion_rate']:.2%}",
            border=True,
        )

    st.success(
        f"**{best['customer_segment'].capitalize()} is the highest-converting "
        f"segment this week at {best['conversion_rate']:.2%}** — prioritise it "
        f"for the Q4 re-engagement ad spend."
    )

    # --- Bar chart: segment x conversion rate ---
    col_chart, col_table = st.columns([3, 2])

    with col_chart:
        with st.container(border=True):
            st.subheader("Conversion rate by segment")
            chart_df = df.assign(
                label=df["conversion_rate"].map(lambda v: f"{v:.2%}"),
                is_best=df["customer_segment"] == best["customer_segment"],
            )
            base = alt.Chart(chart_df).encode(
                x=alt.X(
                    "customer_segment:N",
                    sort=SEGMENT_ORDER,
                    title="Customer value segment",
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y(
                    "conversion_rate:Q",
                    title="Session → purchase conversion",
                    axis=alt.Axis(format="%"),
                ),
            )
            bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                color=alt.condition(
                    alt.datum.is_best,
                    alt.value(ACCENT),
                    alt.value(MUTED),
                ),
                tooltip=[
                    alt.Tooltip("customer_segment:N", title="Segment"),
                    alt.Tooltip("sessions:Q", title="Sessions", format=","),
                    alt.Tooltip("conversions:Q", title="Purchases", format=","),
                    alt.Tooltip("conversion_rate:Q", title="Conversion", format=".2%"),
                ],
            )
            text = base.mark_text(dy=-8, fontWeight="bold").encode(
                text="label:N"
            )
            st.altair_chart(
                (bars + text).properties(height=380), use_container_width=True
            )

    with col_table:
        with st.container(border=True):
            st.subheader("Segment detail")
            display = df.assign(
                conversion_pct=df["conversion_rate"] * 100
            )[
                ["customer_segment", "sessions", "conversions", "conversion_pct"]
            ].rename(
                columns={
                    "customer_segment": "Segment",
                    "sessions": "Sessions",
                    "conversions": "Purchases",
                    "conversion_pct": "Conversion",
                }
            )
            st.dataframe(
                display,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Sessions": st.column_config.NumberColumn(format="%d"),
                    "Purchases": st.column_config.NumberColumn(format="%d"),
                    "Conversion": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )
            st.caption(
                "Quality-gated: segment ∈ {high, medium, low}, no nulls, "
                "conversion_rate ∈ [0, 1], purchases ≤ sessions."
            )


if __name__ == "__main__":
    main()
