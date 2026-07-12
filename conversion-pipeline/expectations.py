"""
Data quality expectations for the session->purchase conversion pipeline.

All checks target the final model `segment_conversion` and run as DAG nodes during
`bauplan run`. Every check is FAIL severity (asserts): if any trips, the numbers going
to the marketing dashboard are untrustworthy and the run must halt.
"""

import bauplan


@bauplan.expectation()
@bauplan.python('3.11')
def test_customer_segment_no_nulls(
    data=bauplan.Model('segment_conversion', columns=['customer_segment']),
):
    """customer_segment must not be null — it is the grouping key for the whole report."""
    from bauplan.standard_expectations import expect_column_no_nulls

    result = expect_column_no_nulls(data, 'customer_segment')
    assert result, 'customer_segment contains null values'
    return result


@bauplan.expectation()
@bauplan.python('3.11')
def test_customer_segment_accepted_values(
    data=bauplan.Model('segment_conversion', columns=['customer_segment']),
):
    """customer_segment must be exactly one of high/medium/low — anything else is a join bug."""
    from bauplan.standard_expectations import expect_column_accepted_values

    result = expect_column_accepted_values(
        data, 'customer_segment', ['high', 'medium', 'low']
    )
    assert result, 'customer_segment has values outside {high, medium, low}'
    return result


@bauplan.expectation()
@bauplan.python('3.11')
def test_conversion_rate_no_nulls(
    data=bauplan.Model('segment_conversion', columns=['conversion_rate']),
):
    """conversion_rate must not be null — a null rate is a broken metric, not a valid answer."""
    from bauplan.standard_expectations import expect_column_no_nulls

    result = expect_column_no_nulls(data, 'conversion_rate')
    assert result, 'conversion_rate contains null values'
    return result


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_conversion_rate_in_unit_interval(
    data=bauplan.Model('segment_conversion', columns=['conversion_rate']),
):
    """conversion_rate must lie in [0, 1] — it is a ratio of converting to total sessions."""
    import polars as pl

    df = pl.from_arrow(data)
    violations = df.filter(
        (pl.col('conversion_rate') < 0.0) | (pl.col('conversion_rate') > 1.0)
    )
    is_valid = violations.height == 0
    assert is_valid, f'{violations.height} rows have conversion_rate outside [0, 1]'
    return is_valid


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_converting_not_exceeding_total(
    data=bauplan.Model(
        'segment_conversion',
        columns=['converting_sessions', 'total_sessions'],
    ),
):
    """converting_sessions must never exceed total_sessions — a converting session is a session."""
    import polars as pl

    df = pl.from_arrow(data).with_columns(
        pl.col('converting_sessions').cast(pl.Int64),
        pl.col('total_sessions').cast(pl.Int64),
    )
    violations = df.filter(pl.col('converting_sessions') > pl.col('total_sessions'))
    is_valid = violations.height == 0
    assert is_valid, f'{violations.height} rows have converting_sessions > total_sessions'
    return is_valid


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_total_sessions_positive(
    data=bauplan.Model('segment_conversion', columns=['total_sessions']),
):
    """total_sessions must be > 0 — a segment with zero sessions is a denominator bug."""
    import polars as pl

    df = pl.from_arrow(data).with_columns(pl.col('total_sessions').cast(pl.Int64))
    violations = df.filter(pl.col('total_sessions') <= 0)
    is_valid = violations.height == 0
    assert is_valid, f'{violations.height} rows have total_sessions <= 0'
    return is_valid
