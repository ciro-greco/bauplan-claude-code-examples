"""
Quality gate for segment_conversion — the table the re-engagement dashboard reads.

All checks are FAIL severity (assert): if any breaks, the numbers driving ad-spend
decisions are untrustworthy, so the run should halt before publish.
"""
import bauplan


@bauplan.expectation()
@bauplan.python('3.11')
def test_segment_accepted_values(data=bauplan.Model('segment_conversion')):
    """customer_segment must be exactly high/medium/low — the dashboard buckets on it."""
    from bauplan.standard_expectations import (
        expect_column_accepted_values,
        expect_column_no_nulls,
    )

    no_nulls = expect_column_no_nulls(data, 'customer_segment')
    assert no_nulls, 'customer_segment contains null values'
    valid = expect_column_accepted_values(
        data, 'customer_segment', ['high', 'medium', 'low']
    )
    assert valid, 'customer_segment has values outside {high, medium, low}'
    return valid


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.42.1'})
def test_conversion_rate_bounds(
    data=bauplan.Model('segment_conversion', columns=['conversion_rate']),
):
    """conversion_rate must be present and a valid probability in [0, 1]."""
    import polars as pl
    from bauplan.standard_expectations import expect_column_no_nulls

    no_nulls = expect_column_no_nulls(data, 'conversion_rate')
    assert no_nulls, 'conversion_rate contains null values'

    df = pl.from_arrow(data)
    out_of_range = df.filter(
        (pl.col('conversion_rate') < 0.0) | (pl.col('conversion_rate') > 1.0)
    )
    is_valid = out_of_range.height == 0
    assert is_valid, f'{out_of_range.height} rows have conversion_rate outside [0, 1]'
    return is_valid


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.42.1'})
def test_session_counts_positive_and_consistent(
    data=bauplan.Model(
        'segment_conversion',
        columns=['total_sessions', 'converted_sessions'],
    ),
):
    """
    total_sessions and converted_sessions must be non-null and > 0, and a segment
    can't convert more sessions than it had (converted_sessions <= total_sessions).
    """
    import polars as pl
    from bauplan.standard_expectations import expect_column_no_nulls

    for col in ('total_sessions', 'converted_sessions'):
        assert expect_column_no_nulls(data, col), f'{col} contains null values'

    df = pl.from_arrow(data)
    non_positive = df.filter(
        (pl.col('total_sessions') <= 0) | (pl.col('converted_sessions') <= 0)
    )
    assert non_positive.height == 0, (
        f'{non_positive.height} rows have non-positive session counts'
    )

    over_converted = df.filter(pl.col('converted_sessions') > pl.col('total_sessions'))
    is_valid = over_converted.height == 0
    assert is_valid, (
        f'{over_converted.height} rows have converted_sessions > total_sessions'
    )
    return is_valid
