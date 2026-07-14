"""
Data quality gate for `segment_conversion` — the table the marketing team acts on
to allocate Q4 re-engagement ad spend. Every check is FAIL severity: if the
conversion table is wrong, budget goes to the wrong segment.
"""
import bauplan


@bauplan.expectation()
@bauplan.python('3.11')
def test_segment_accepted_values(data=bauplan.Model('segment_conversion')):
    """customer_segment must be exactly high/medium/low — the report is keyed on it."""
    from bauplan.standard_expectations import (
        expect_column_accepted_values,
        expect_column_no_nulls,
    )

    no_nulls = expect_column_no_nulls(data, 'customer_segment')
    assert no_nulls, 'customer_segment contains null values'

    accepted = expect_column_accepted_values(
        data, 'customer_segment', ['high', 'medium', 'low']
    )
    assert accepted, 'customer_segment has values outside high/medium/low'
    return accepted


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_counts_positive(
    data=bauplan.Model(
        'segment_conversion',
        columns=[
            'total_sessions',
            'converted_sessions',
            'purchase_events',
            'unique_users',
        ],
    )
):
    """All volume columns must be present and strictly positive — a zero means a
    broken join or an empty segment, which would silently understate a segment."""
    import polars as pl

    df = pl.from_arrow(data)
    cols = ['total_sessions', 'converted_sessions', 'purchase_events', 'unique_users']
    for col in cols:
        nulls = df.select(pl.col(col).is_null().sum()).item()
        assert nulls == 0, f'{col} has {nulls} null(s)'
        non_positive = df.filter(pl.col(col) <= 0).height
        assert non_positive == 0, f'{col} has {non_positive} row(s) <= 0'
    return True


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_conversion_rate_bounds(
    data=bauplan.Model('segment_conversion', columns=['conversion_rate'])
):
    """conversion_rate is a proportion — must be non-null and within [0, 1]."""
    import polars as pl

    df = pl.from_arrow(data)
    nulls = df.select(pl.col('conversion_rate').is_null().sum()).item()
    assert nulls == 0, f'conversion_rate has {nulls} null(s)'
    out_of_range = df.filter(
        (pl.col('conversion_rate') < 0) | (pl.col('conversion_rate') > 1)
    ).height
    assert out_of_range == 0, f'{out_of_range} conversion_rate value(s) outside [0, 1]'
    return True


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_converted_not_exceeding_total(
    data=bauplan.Model(
        'segment_conversion', columns=['converted_sessions', 'total_sessions']
    )
):
    """converted_sessions can never exceed total_sessions — it's a subset by definition."""
    import polars as pl

    df = pl.from_arrow(data)
    violations = df.filter(
        pl.col('converted_sessions') > pl.col('total_sessions')
    ).height
    assert violations == 0, f'{violations} row(s) have converted > total sessions'
    return True
