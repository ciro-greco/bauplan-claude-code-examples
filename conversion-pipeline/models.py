"""
Session -> Purchase Conversion by Customer Segment
==================================================

Q4 re-engagement campaign support. For this week's shopping activity, compute the
session->purchase conversion rate for each customer value segment (high / medium / low),
so marketing can see which segments are worth the ad spend.

DAG
---
  bauplan.ecommerce_sessions_week ──▶ session_flags ─┐
                                                     ├─▶ segment_conversion
  bauplan.ecommerce_users ───────────────────────────┘

Definitions
-----------
  session            = one distinct `user_session`
  converting session = a session with >= 1 event_type == 'purchase'
  conversion_rate    = converting_sessions / total_sessions   (in [0, 1])
"""

import bauplan


@bauplan.model()
@bauplan.python('3.11', pip={'duckdb': '1.2.0'})
def session_flags(
    sessions=bauplan.Model(
        'ecommerce_sessions_week',
        # I/O pushdown: only the columns needed to identify a session + its purchase flag
        columns=['user_session', 'user_id', 'event_type'],
        filter="user_session IS NOT NULL AND user_id IS NOT NULL",
    ),
):
    """
    Collapse raw events to one row per session with a purchase flag and its user_id.

    | user_session | user_id | did_purchase |
    |--------------|---------|--------------|
    | a1b2c3       | 5150    | 1            |
    | d4e5f6       | 8291    | 0            |
    """
    import duckdb

    return duckdb.sql("""
        SELECT
            user_session,
            MAX(user_id) AS user_id,
            MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS did_purchase
        FROM sessions
        GROUP BY user_session
    """).arrow()


@bauplan.model(
    columns=['customer_segment', 'total_sessions', 'converting_sessions', 'conversion_rate'],
    materialization_strategy='REPLACE',
)
@bauplan.python('3.11', pip={'duckdb': '1.2.0'})
def segment_conversion(
    flags=bauplan.Model('session_flags'),
    users=bauplan.Model(
        'ecommerce_users',
        columns=['user_id', 'customer_segment'],
    ),
):
    """
    Session->purchase conversion rate per customer value segment.

    | customer_segment | total_sessions | converting_sessions | conversion_rate |
    |------------------|----------------|---------------------|-----------------|
    | high             | 210345         | 18922               | 0.0900          |
    | medium           | 420110         | 21005               | 0.0500          |
    | low              | 190876         | 4780                | 0.0250          |
    """
    import duckdb

    return duckdb.sql("""
        SELECT
            u.customer_segment,
            COUNT(*)                                          AS total_sessions,
            SUM(f.did_purchase)                               AS converting_sessions,
            CAST(SUM(f.did_purchase) AS DOUBLE) / COUNT(*)    AS conversion_rate
        FROM flags AS f
        JOIN users AS u ON f.user_id = u.user_id
        WHERE u.customer_segment IS NOT NULL
        GROUP BY u.customer_segment
        ORDER BY conversion_rate DESC
    """).arrow()
