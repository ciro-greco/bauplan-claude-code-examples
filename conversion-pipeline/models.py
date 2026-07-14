"""
Q4 Re-engagement — session→purchase conversion by customer value segment
========================================================================

DAG:

    [ecommerce_sessions_week] ──→ [session_conversion] ──→ [conversion_by_segment]
    [ecommerce_users] ─────────────────────────────────────┘

- `session_conversion` collapses raw events to one row per session, flagging
  whether the session contained a purchase.
- `conversion_by_segment` joins sessions to users and computes the
  session→purchase conversion rate for each customer value segment.
"""

import bauplan


@bauplan.model()
@bauplan.python("3.11", pip={"duckdb": "1.2.0"})
def session_conversion(
    sessions=bauplan.Model(
        "ecommerce_sessions_week",
        columns=["user_session", "user_id", "event_type"],
    ),
):
    """
    One row per session, with a flag for whether it converted to a purchase.

    | user_session | user_id | converted |
    |--------------|---------|-----------|
    | a1b2-...     | 5423    | 1         |
    | c3d4-...     | 9981    | 0         |
    """
    import duckdb

    con = duckdb.connect()
    con.register("sessions", sessions)
    return con.execute(
        """
        SELECT
            user_session,
            -- a session maps to a single user; take any user_id for it
            MAX(user_id) AS user_id,
            MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS converted
        FROM sessions
        WHERE user_session IS NOT NULL
        GROUP BY user_session
        """
    ).arrow()


@bauplan.model(
    columns=[
        "customer_segment",
        "total_sessions",
        "converting_sessions",
        "conversion_rate",
    ],
    materialization_strategy="REPLACE",
)
@bauplan.python("3.11", pip={"duckdb": "1.2.0"})
def conversion_by_segment(
    sessions=bauplan.Model("session_conversion"),
    users=bauplan.Model(
        "ecommerce_users",
        columns=["user_id", "customer_segment"],
    ),
):
    """
    Session→purchase conversion rate per customer value segment.

    | customer_segment | total_sessions | converting_sessions | conversion_rate |
    |------------------|----------------|---------------------|-----------------|
    | high             | 251034         | 18227               | 0.0726          |
    | medium           | 503118         | 21044               | 0.0418          |
    | low              | 250901         | 6012                | 0.0240          |
    """
    import duckdb

    con = duckdb.connect()
    con.register("sessions", sessions)
    con.register("users", users)
    return con.execute(
        """
        SELECT
            u.customer_segment,
            COUNT(*)                              AS total_sessions,
            SUM(s.converted)                      AS converting_sessions,
            ROUND(SUM(s.converted) * 1.0 / COUNT(*), 4) AS conversion_rate
        FROM sessions s
        JOIN users u ON s.user_id = u.user_id
        WHERE u.customer_segment IS NOT NULL
        GROUP BY u.customer_segment
        ORDER BY conversion_rate DESC
        """
    ).arrow()
