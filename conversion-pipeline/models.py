"""
Q4 re-engagement: session -> purchase conversion rate per customer value segment.

DAG:
  [bauplan.ecommerce_sessions_week] --> session_segments --> segment_conversion
  [bauplan.ecommerce_users] ----------------^

A "session" is one `user_session`. It "converts" if it contains at least one
`purchase` event. Each session is attributed to the customer's value segment
(high / medium / low) via a join on user_id.
"""
import bauplan


@bauplan.model()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def session_segments(
    sessions=bauplan.Model(
        'ecommerce_sessions_week',
        columns=['user_session', 'user_id', 'event_type'],
    ),
    users=bauplan.Model(
        'ecommerce_users',
        columns=['user_id', 'customer_segment'],
    ),
):
    """
    One row per session, tagged with its value segment and whether it converted.

    | user_session | customer_segment | converted | purchase_events |
    |--------------|------------------|-----------|-----------------|
    | a1b2...      | high             | 1         | 2               |
    """
    import polars as pl

    s = pl.from_arrow(sessions)
    u = pl.from_arrow(users)

    # Segment is a per-user attribute; take one row per user_id to avoid fan-out.
    u = u.unique(subset=['user_id'])

    s = s.join(u, on='user_id', how='inner')

    # Collapse events to one row per session within a segment.
    per_session = s.group_by(['user_session', 'customer_segment']).agg(
        purchase_events=(pl.col('event_type') == 'purchase').sum(),
        user_id=pl.col('user_id').first(),
    )
    per_session = per_session.with_columns(
        converted=(pl.col('purchase_events') > 0).cast(pl.Int64)
    )
    return per_session.to_arrow()


@bauplan.model(
    columns=[
        'customer_segment',
        'total_sessions',
        'converted_sessions',
        'conversion_rate',
        'purchase_events',
        'unique_users',
    ],
    materialization_strategy='REPLACE',
)
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def segment_conversion(
    data=bauplan.Model('session_segments'),
):
    """
    One row per customer value segment with session->purchase conversion.

    | customer_segment | total_sessions | converted_sessions | conversion_rate | purchase_events | unique_users |
    |------------------|----------------|--------------------|-----------------|-----------------|--------------|
    | high             | 120000         | 18000              | 0.15            | 21000           | 40000        |
    """
    import polars as pl

    df = pl.from_arrow(data)

    agg = df.group_by('customer_segment').agg(
        total_sessions=pl.col('user_session').n_unique(),
        converted_sessions=pl.col('converted').sum(),
        purchase_events=pl.col('purchase_events').sum(),
        unique_users=pl.col('user_id').n_unique(),
    )
    agg = agg.with_columns(
        conversion_rate=(
            pl.col('converted_sessions') / pl.col('total_sessions')
        ).round(6)
    )

    # Order high / medium / low.
    order = pl.DataFrame(
        {'customer_segment': ['high', 'medium', 'low'], '__ord': [0, 1, 2]}
    )
    agg = (
        agg.join(order, on='customer_segment', how='left')
        .sort('__ord')
        .drop('__ord')
        .select(
            'customer_segment',
            'total_sessions',
            'converted_sessions',
            'conversion_rate',
            'purchase_events',
            'unique_users',
        )
    )
    return agg.to_arrow()
