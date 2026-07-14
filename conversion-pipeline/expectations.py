import bauplan


@bauplan.expectation()
@bauplan.python('3.11')
def test_segment_accepted_values(data=bauplan.Model('segment_conversion')):
    """customer_segment must be one of high/medium/low — the whole report is keyed by it."""
    from bauplan.standard_expectations import expect_column_accepted_values

    result = expect_column_accepted_values(
        data, 'customer_segment', ['high', 'medium', 'low']
    )
    assert result, 'customer_segment contains values outside {high, medium, low}'
    return result


@bauplan.expectation()
@bauplan.python('3.11')
def test_segment_no_nulls(data=bauplan.Model('segment_conversion')):
    """customer_segment is the grouping key — a null segment means a broken join."""
    from bauplan.standard_expectations import expect_column_no_nulls

    result = expect_column_no_nulls(data, 'customer_segment')
    assert result, 'customer_segment contains null values'
    return result


@bauplan.expectation()
@bauplan.python('3.11')
def test_segment_unique(data=bauplan.Model('segment_conversion')):
    """Exactly one row per segment — duplicates would double-count sessions."""
    from bauplan.standard_expectations import expect_column_all_unique

    result = expect_column_all_unique(data, 'customer_segment')
    assert result, 'customer_segment has duplicate rows'
    return result


@bauplan.expectation()
@bauplan.python('3.11')
def test_exactly_three_segments(data=bauplan.Model('segment_conversion')):
    """There are three value segments — fewer means a segment produced no sessions."""
    row_count = data.num_rows
    assert row_count == 3, f'expected 3 segment rows, got {row_count}'
    return row_count == 3


@bauplan.expectation()
@bauplan.python('3.11')
def test_metric_columns_no_nulls(data=bauplan.Model('segment_conversion')):
    """The numeric metrics feed the dashboard directly — nulls would render blanks."""
    from bauplan.standard_expectations import expect_column_no_nulls

    ok = True
    for col in ('total_sessions', 'converted_sessions', 'conversion_rate'):
        result = expect_column_no_nulls(data, col)
        assert result, f'{col} contains null values'
        ok = ok and result
    return ok


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_conversion_rate_in_unit_interval(
    data=bauplan.Model('segment_conversion', columns=['conversion_rate']),
):
    """conversion_rate is a proportion — must sit in [0, 1] or the math is wrong."""
    import polars as pl

    df = pl.from_arrow(data)
    violations = df.filter(
        (pl.col('conversion_rate') < 0) | (pl.col('conversion_rate') > 1)
    )
    is_valid = violations.height == 0
    assert is_valid, f'{violations.height} rows have conversion_rate outside [0, 1]'
    return is_valid


@bauplan.expectation()
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def test_converted_not_exceed_total(
    data=bauplan.Model(
        'segment_conversion', columns=['total_sessions', 'converted_sessions']
    ),
):
    """converted_sessions is a subset of total_sessions — exceeding it is impossible."""
    import polars as pl

    df = pl.from_arrow(data)
    violations = df.filter(pl.col('converted_sessions') > pl.col('total_sessions'))
    is_valid = violations.height == 0
    assert is_valid, f'{violations.height} rows have converted_sessions > total_sessions'
    return is_valid
