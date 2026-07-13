"""
Data quality expectations for the conversion pipeline.

All checks target the final model output `segment_conversion` and run as DAG
nodes during `bauplan run`. Every check is FAIL severity (asserts): the result
table feeds a marketing spend decision, so a violation must halt publishing.
"""

import bauplan

SEGMENTS = ['high', 'medium', 'low']


@bauplan.expectation()
@bauplan.python('3.11')
def test_customer_segment_no_nulls(data=bauplan.Model('segment_conversion')):
    """customer_segment must never be null — it is the reporting key."""
    from bauplan.standard_expectations import expect_column_no_nulls

    result = expect_column_no_nulls(data, 'customer_segment')
    assert result, 'customer_segment contains null values'
    return result


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_customer_segment_exact_set(data=bauplan.Model('segment_conversion')):
    """Segments must be exactly {high, medium, low} — no missing, no unexpected."""
    import polars as pl

    df = pl.from_arrow(data)
    found = set(df.get_column('customer_segment').to_list())
    is_valid = found == set(SEGMENTS)
    assert is_valid, f'customer_segment set is {sorted(found)}, expected {sorted(SEGMENTS)}'
    return is_valid


@bauplan.expectation()
@bauplan.python('3.11')
def test_conversion_rate_no_nulls(data=bauplan.Model('segment_conversion')):
    """conversion_rate must never be null — it is the headline metric."""
    from bauplan.standard_expectations import expect_column_no_nulls

    result = expect_column_no_nulls(data, 'conversion_rate')
    assert result, 'conversion_rate contains null values'
    return result


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_conversion_rate_in_unit_interval(data=bauplan.Model('segment_conversion')):
    """conversion_rate is a proportion — must sit within [0, 1]."""
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
def test_converting_not_exceeding_total(data=bauplan.Model('segment_conversion')):
    """converting_sessions can never exceed total_sessions — a subset can't be larger."""
    import polars as pl

    df = pl.from_arrow(data)
    violations = df.filter(pl.col('converting_sessions') > pl.col('total_sessions'))
    is_valid = violations.height == 0
    assert is_valid, f'{violations.height} rows have converting_sessions > total_sessions'
    return is_valid


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_total_sessions_positive(data=bauplan.Model('segment_conversion')):
    """Every segment must have at least one session — a zero denominator is meaningless."""
    import polars as pl

    df = pl.from_arrow(data)
    violations = df.filter(pl.col('total_sessions') <= 0)
    is_valid = violations.height == 0
    assert is_valid, f'{violations.height} segments have total_sessions <= 0'
    return is_valid
