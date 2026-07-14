"""
Q4 re-engagement — session→purchase conversion by customer value segment.

DAG:
  [bauplan.ecommerce_sessions_week] ─→ session_purchase ─┐
                                                          ├─→ segment_conversion
  [bauplan.ecommerce_users] ──────────────────────────────┘

session_purchase   : one row per user_session — its user_id and whether it converted.
segment_conversion : conversion rate per customer_segment (high/medium/low).
"""
import bauplan


@bauplan.model()
@bauplan.python('3.11', pip={'duckdb': '1.1.3'})
def session_purchase(
    sessions=bauplan.Model(
        'bauplan.ecommerce_sessions_week',
        columns=['user_session', 'user_id', 'event_type'],
    ),
):
    """
    Collapse the event stream to one row per session: which user it belongs to,
    and whether that session contained at least one purchase event.

    | user_session | user_id   | purchased |
    |--------------|-----------|-----------|
    | 29cd204d-... | 513341998 | 0         |
    | 24513f4c-... | 530162018 | 1         |
    """
    import duckdb

    con = duckdb.connect()
    con.register('sessions', sessions)
    return con.execute(
        """
        SELECT
            user_session,
            -- a session belongs to a single user; take any observed user_id
            MAX(user_id) AS user_id,
            MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS purchased
        FROM sessions
        WHERE user_session IS NOT NULL
        GROUP BY user_session
        """
    ).arrow()


@bauplan.model(
    columns=['customer_segment', 'total_sessions', 'converted_sessions', 'conversion_rate'],
    materialization_strategy='REPLACE',
)
@bauplan.python('3.11', pip={'duckdb': '1.1.3'})
def segment_conversion(
    session_purchase=bauplan.Model('session_purchase'),
    users=bauplan.Model(
        'bauplan.ecommerce_users',
        columns=['user_id', 'customer_segment'],
    ),
):
    """
    Join sessions to their owner's value segment and compute session→purchase
    conversion per segment. Sessions whose user_id has no segment are dropped.

    | customer_segment | total_sessions | converted_sessions | conversion_rate |
    |------------------|----------------|--------------------|-----------------|
    | high             | 210345         | 41022              | 0.1950          |
    | medium           | 512908         | 68110              | 0.1328          |
    | low              | 190412         | 12233              | 0.0642          |
    """
    import duckdb

    con = duckdb.connect()
    con.register('session_purchase', session_purchase)
    con.register('users', users)
    return con.execute(
        """
        SELECT
            u.customer_segment,
            COUNT(*)                                        AS total_sessions,
            SUM(sp.purchased)                               AS converted_sessions,
            ROUND(SUM(sp.purchased) * 1.0 / COUNT(*), 4)    AS conversion_rate
        FROM session_purchase sp
        JOIN users u USING (user_id)
        WHERE u.customer_segment IS NOT NULL
        GROUP BY u.customer_segment
        ORDER BY conversion_rate DESC
        """
    ).arrow()
