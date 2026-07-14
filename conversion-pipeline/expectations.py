"""
Data quality expectations for the conversion pipeline.

These gate the final `conversion_by_segment` table — the numbers the marketing
team acts on. All are FAIL-severity (assert): if any breaks, the segment
conversion rates are unsafe to publish.
"""

import bauplan


@bauplan.expectation()
@bauplan.python("3.11")
def test_segment_no_nulls(
    data=bauplan.Model("conversion_by_segment", columns=["customer_segment"]),
):
    """customer_segment must never be null — it is the reporting key."""
    from bauplan.standard_expectations import expect_column_no_nulls

    result = expect_column_no_nulls(data, "customer_segment")
    assert result, "customer_segment contains null values"
    return result


@bauplan.expectation()
@bauplan.python("3.11")
def test_segment_accepted_values(
    data=bauplan.Model("conversion_by_segment", columns=["customer_segment"]),
):
    """customer_segment must be exactly one of high / medium / low."""
    from bauplan.standard_expectations import expect_column_accepted_values

    result = expect_column_accepted_values(
        data, "customer_segment", ["high", "medium", "low"]
    )
    assert result, "customer_segment contains values outside {high, medium, low}"
    return result


@bauplan.expectation()
@bauplan.python("3.11")
def test_conversion_rate_no_nulls(
    data=bauplan.Model("conversion_by_segment", columns=["conversion_rate"]),
):
    """conversion_rate must never be null — it is the headline metric."""
    from bauplan.standard_expectations import expect_column_no_nulls

    result = expect_column_no_nulls(data, "conversion_rate")
    assert result, "conversion_rate contains null values"
    return result


@bauplan.expectation()
@bauplan.python("3.11", pip={"polars": "1.15.0"})
def test_conversion_rate_in_unit_interval(
    data=bauplan.Model("conversion_by_segment", columns=["conversion_rate"]),
):
    """conversion_rate must lie in [0, 1] — it is a ratio, anything else is a bug."""
    import polars as pl

    df = pl.from_arrow(data)
    violations = df.filter(
        (pl.col("conversion_rate") < 0) | (pl.col("conversion_rate") > 1)
    )
    is_valid = violations.height == 0
    assert is_valid, f"{violations.height} rows have conversion_rate outside [0, 1]"
    return is_valid


@bauplan.expectation()
@bauplan.python("3.11", pip={"polars": "1.15.0"})
def test_counts_non_negative(
    data=bauplan.Model(
        "conversion_by_segment",
        columns=["total_sessions", "converting_sessions"],
    ),
):
    """Session counts must be present and non-negative, and conversions <= totals."""
    import polars as pl

    df = pl.from_arrow(data)
    null_count = (
        df.select(
            pl.col("total_sessions").is_null().sum()
            + pl.col("converting_sessions").is_null().sum()
        ).item()
    )
    assert null_count == 0, "session count columns contain nulls"

    violations = df.filter(
        (pl.col("total_sessions") < 0)
        | (pl.col("converting_sessions") < 0)
        | (pl.col("converting_sessions") > pl.col("total_sessions"))
    )
    is_valid = violations.height == 0
    assert is_valid, f"{violations.height} rows have invalid session counts"
    return is_valid
