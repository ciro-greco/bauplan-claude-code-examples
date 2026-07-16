"""
Data quality gate for the session -> purchase conversion pipeline.

Every check runs against the final output table `segment_conversion` as a DAG
node during `bauplan run`, right after the model materializes. All are FAIL
severity (assert): if any trips, the numbers are not safe to steer Q4 ad spend
with, so the run halts before the table can be published.
"""

import bauplan


@bauplan.expectation()
@bauplan.python('3.11')
def test_segment_accepted_values(
    data=bauplan.Model('segment_conversion', columns=['customer_segment']),
):
    """customer_segment must be exactly one of high / medium / low.

    The whole report is sliced by segment; an unexpected label means the join
    to ecommerce_users leaked bad data and the breakdown is untrustworthy.
    """
    from bauplan.standard_expectations import expect_column_accepted_values

    result = expect_column_accepted_values(
        data, 'customer_segment', ['high', 'medium', 'low']
    )
    assert result, 'customer_segment has values outside {high, medium, low}'
    return result


@bauplan.expectation()
@bauplan.python('3.11')
def test_segment_no_nulls(
    data=bauplan.Model('segment_conversion', columns=['customer_segment']),
):
    """customer_segment must have no nulls — every row must belong to a segment."""
    from bauplan.standard_expectations import expect_column_no_nulls

    result = expect_column_no_nulls(data, 'customer_segment')
    assert result, 'customer_segment contains nulls'
    return result


@bauplan.expectation()
@bauplan.python('3.11')
def test_conversion_rate_bounds(
    data=bauplan.Model('segment_conversion', columns=['conversion_rate']),
):
    """conversion_rate must be non-null and within [0, 1].

    It is conversions / sessions — a value outside [0, 1] is arithmetically
    impossible and would produce a misleading headline percentage.
    """
    import pyarrow.compute as pc

    col = data.column('conversion_rate')
    assert col.null_count == 0, 'conversion_rate contains nulls'
    lo = pc.min(col).as_py()
    hi = pc.max(col).as_py()
    ok = lo >= 0.0 and hi <= 1.0
    assert ok, f'conversion_rate outside [0, 1]: min={lo}, max={hi}'
    return ok


@bauplan.expectation()
@bauplan.python('3.11')
def test_counts_non_negative(
    data=bauplan.Model(
        'segment_conversion', columns=['sessions', 'conversions']
    ),
):
    """sessions and conversions must be non-null and non-negative counts."""
    import pyarrow.compute as pc

    for name in ('sessions', 'conversions'):
        col = data.column(name)
        assert col.null_count == 0, f'{name} contains nulls'
        assert pc.min(col).as_py() >= 0, f'{name} has negative values'
    return True


@bauplan.expectation()
@bauplan.python('3.11')
def test_conversions_not_exceeding_sessions(
    data=bauplan.Model(
        'segment_conversion', columns=['sessions', 'conversions']
    ),
):
    """conversions must never exceed sessions.

    A session converts at most once, so conversions <= sessions per segment.
    A violation means the session-dedup logic broke.
    """
    import pyarrow.compute as pc

    violations = pc.sum(
        pc.cast(
            pc.greater(data.column('conversions'), data.column('sessions')),
            'int64',
        )
    ).as_py()
    ok = violations == 0
    assert ok, f'{violations} segment(s) have conversions > sessions'
    return ok
