import bauplan


@bauplan.model()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def session_flags(
    sessions=bauplan.Model(
        'ecommerce_sessions_week',
        columns=['user_session', 'user_id', 'event_type'],
    ),
):
    """
    Collapse the raw event stream to one row per session, flagging whether the
    session contained a purchase and carrying the session's user_id for the join.

    | user_session | user_id | converted |
    |--------------|---------|-----------|
    | a1b2...      | 5512    | 1         |
    | c3d4...      | 9931    | 0         |
    """
    import polars as pl

    df = pl.from_arrow(sessions)
    return (
        df.group_by('user_session')
        .agg(
            pl.col('user_id').first().alias('user_id'),
            (pl.col('event_type') == 'purchase').any().cast(pl.Int64).alias('converted'),
        )
        .to_arrow()
    )


@bauplan.model()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def session_segments(
    sessions=bauplan.Model('session_flags'),
    users=bauplan.Model(
        'ecommerce_users',
        columns=['user_id', 'customer_segment'],
    ),
):
    """
    Attach each session's customer value segment by joining on user_id.

    | user_session | customer_segment | converted |
    |--------------|------------------|-----------|
    | a1b2...      | high             | 1         |
    | c3d4...      | low              | 0         |
    """
    import polars as pl

    s = pl.from_arrow(sessions)
    u = pl.from_arrow(users)
    return (
        s.join(u, on='user_id', how='inner')
        .select('user_session', 'customer_segment', 'converted')
        .to_arrow()
    )


@bauplan.model(
    columns=['customer_segment', 'total_sessions', 'converted_sessions', 'conversion_rate'],
    materialization_strategy='REPLACE',
)
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def segment_conversion(
    sessions=bauplan.Model('session_segments'),
):
    """
    Session -> purchase conversion rate per customer value segment.
    One row per segment; conversion_rate = converted_sessions / total_sessions.

    | customer_segment | total_sessions | converted_sessions | conversion_rate |
    |------------------|----------------|--------------------|-----------------|
    | high             | 210334         | 18240              | 0.0867          |
    | medium           | 420112         | 21005              | 0.0500          |
    | low              | 209880         | 6296               | 0.0300          |
    """
    import polars as pl

    df = pl.from_arrow(sessions)
    return (
        df.group_by('customer_segment')
        .agg(
            pl.len().alias('total_sessions'),
            pl.col('converted').sum().alias('converted_sessions'),
        )
        .with_columns(
            (pl.col('converted_sessions') / pl.col('total_sessions'))
            .round(4)
            .alias('conversion_rate')
        )
        .sort('conversion_rate', descending=True)
        .to_arrow()
    )
