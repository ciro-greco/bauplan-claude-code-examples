"""
Q4 re-engagement — session -> purchase conversion by customer value segment
===========================================================================

This week's shopping activity, reduced to one question: for each customer
value segment (high / medium / low), what share of sessions ended in a
purchase? That's the signal for where the Q4 ad spend actually pays off.

DAG:

    [bauplan.ecommerce_sessions_week] ──→ [sessions_scored] ──→ [segment_conversion]
    [bauplan.ecommerce_users] ───────────────────────────────────────┘

- sessions_scored:     collapse raw events to one row per session, flag whether
                       the session contained a purchase.
- segment_conversion:  join sessions to their owner's value segment and compute
                       the conversion rate per segment (final output table).
"""

import bauplan


@bauplan.model()
@bauplan.python('3.11', pip={'duckdb': '1.2.0'})
def sessions_scored(
    events=bauplan.Model(
        'ecommerce_sessions_week',
        columns=['user_session', 'user_id', 'event_type'],
    ),
):
    """
    Collapse raw session events to one row per session, flagging conversion.

    A session (user_session) converts if it contains any 'purchase' event.

    | user_session | user_id   | converted |
    |--------------|-----------|-----------|
    | e2adf039-... | 522351929 | 0         |
    | 778c4c69-... | 542977421 | 1         |
    """
    import duckdb

    return duckdb.sql("""
        SELECT
            user_session,
            any_value(user_id) AS user_id,
            MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS converted
        FROM events
        WHERE user_session IS NOT NULL
        GROUP BY user_session
    """).arrow()


@bauplan.model(
    columns=['customer_segment', 'sessions', 'conversions', 'conversion_rate'],
    materialization_strategy='REPLACE',
)
@bauplan.python('3.11', pip={'duckdb': '1.2.0'})
def segment_conversion(
    sessions=bauplan.Model('sessions_scored'),
    users=bauplan.Model(
        'ecommerce_users',
        columns=['user_id', 'customer_segment'],
    ),
):
    """
    Session -> purchase conversion rate per customer value segment.

    Inner join keeps only sessions whose user has a known value segment, so
    customer_segment is always one of high / medium / low (no nulls).

    | customer_segment | sessions | conversions | conversion_rate |
    |------------------|----------|-------------|-----------------|
    | high             | 755358   | 51200       | 0.0678          |
    | medium           | 1510785  | 109800      | 0.0727          |
    | low              | 755292   | 48100       | 0.0637          |
    """
    import duckdb

    return duckdb.sql("""
        SELECT
            u.customer_segment                              AS customer_segment,
            COUNT(*)                                        AS sessions,
            SUM(s.converted)                                AS conversions,
            CAST(SUM(s.converted) AS DOUBLE) / COUNT(*)     AS conversion_rate
        FROM sessions AS s
        JOIN users AS u ON s.user_id = u.user_id
        WHERE u.customer_segment IS NOT NULL
        GROUP BY u.customer_segment
        ORDER BY conversion_rate DESC
    """).arrow()
