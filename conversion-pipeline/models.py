"""
Session -> purchase conversion by customer value segment
========================================================

Reads this week's ecommerce sessions, flags each session as converting if it
contains a purchase event, joins each session's user to its value segment
(high / medium / low), and reports the conversion rate per segment.

DAG:
    [bauplan.ecommerce_sessions_week] -> [session_conversion_flags] -> [segment_conversion]
    [bauplan.ecommerce_users] ----------------------------------------^
"""

import bauplan


@bauplan.model()
@bauplan.python('3.11', pip={'duckdb': '1.2.0'})
def session_conversion_flags(
    sessions=bauplan.Model(
        'ecommerce_sessions_week',
        columns=['user_session', 'user_id', 'event_type'],
    ),
):
    """
    Collapses raw session events to one row per session, flagging conversion.
    A session converts if it has at least one purchase event.

    | user_session | user_id | converted |
    |--------------|---------|-----------|
    | a1b2c3       | 42      | 1         |
    """
    import duckdb

    return duckdb.sql("""
        SELECT
            user_session,
            user_id,
            MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS converted
        FROM sessions
        WHERE user_session IS NOT NULL
          AND user_id IS NOT NULL
        GROUP BY user_session, user_id
    """).arrow()


@bauplan.model(
    columns=['customer_segment', 'total_sessions', 'converting_sessions', 'conversion_rate'],
    materialization_strategy='REPLACE',
)
@bauplan.python('3.11', pip={'duckdb': '1.2.0'})
def segment_conversion(
    flags=bauplan.Model('session_conversion_flags'),
    users=bauplan.Model(
        'ecommerce_users',
        columns=['user_id', 'customer_segment'],
    ),
):
    """
    Session -> purchase conversion rate per customer value segment.
    Inner join drops the handful of sessions with no matching user, so
    customer_segment is always one of {high, medium, low}, never null.

    | customer_segment | total_sessions | converting_sessions | conversion_rate |
    |------------------|----------------|---------------------|-----------------|
    | high             | 755000         | 50500               | 0.0669          |
    """
    import duckdb

    return duckdb.sql("""
        SELECT
            users.customer_segment                                    AS customer_segment,
            COUNT(*)                                                  AS total_sessions,
            SUM(flags.converted)                                      AS converting_sessions,
            CAST(SUM(flags.converted) AS DOUBLE) / COUNT(*)           AS conversion_rate
        FROM flags
        JOIN users ON flags.user_id = users.user_id
        WHERE users.customer_segment IS NOT NULL
        GROUP BY users.customer_segment
    """).arrow()
