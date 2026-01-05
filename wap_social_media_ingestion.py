"""
WAP (Write-Audit-Publish) script for social media data ingestion.

Production-ready version with comprehensive data quality checks.
Imports data from S3 into the bauplan lakehouse using the WAP pattern
for safe data loading with quality validation.

Data Quality Tiers:
- Tier 1 (Critical): user_id, user_engagement_score, time_on_feed_per_day
- Tier 2 (Important): perceived_stress_score, self_reported_happiness, age
- Tier 3 (Recommended): Platform metrics (active_minutes, sessions, followers)
"""

import bauplan
from datetime import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class DataQualityResult:
    """Results from data quality validation."""

    passed: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    critical_failures: list[str]
    warnings: list[str]
    row_count: int
    null_summary: dict[str, int]


def run_data_quality_checks(
    client: bauplan.Client,
    table_name: str,
    namespace: str,
    branch_name: str,
    min_rows: int = 100_000,
) -> DataQualityResult:
    """
    Run comprehensive data quality checks on imported data.

    Args:
        client: Bauplan client
        table_name: Name of the table to validate
        namespace: Namespace of the table
        branch_name: Branch to query
        min_rows: Minimum expected row count

    Returns:
        DataQualityResult with validation results
    """
    fq_table = f"{namespace}.{table_name}"
    critical_failures = []
    warnings = []
    null_summary = {}

    print("\n" + "=" * 60)
    print("DATA QUALITY AUDIT")
    print("=" * 60)

    # =========================================================================
    # CHECK 1: Row Count
    # =========================================================================
    print("\n[1/6] Checking row count...")
    result = client.query(
        query=f"SELECT COUNT(*) as cnt FROM {fq_table}",
        ref=branch_name
    )
    row_count = result.column("cnt")[0].as_py()
    print(f"       Total rows: {row_count:,}")

    if row_count < min_rows:
        critical_failures.append(
            f"Row count ({row_count:,}) below minimum ({min_rows:,})"
        )
        print(f"       CRITICAL: Below minimum threshold of {min_rows:,}")
    else:
        print(f"       PASSED: Meets minimum threshold")

    # =========================================================================
    # CHECK 2: Null Values in Critical Columns (Tier 1)
    # =========================================================================
    print("\n[2/6] Checking Tier 1 columns (Critical - no nulls allowed)...")

    tier1_columns = [
        ('user_id', 'Primary identifier'),
        ('user_engagement_score', 'Primary target metric'),
        ('time_on_feed_per_day', 'Secondary target metric'),
    ]

    for col, description in tier1_columns:
        result = client.query(
            query=f"SELECT COUNT(*) - COUNT({col}) as null_count FROM {fq_table}",
            ref=branch_name
        )
        null_count = result.column("null_count")[0].as_py()
        null_summary[col] = null_count

        if null_count > 0:
            critical_failures.append(f"{col}: {null_count:,} null values")
            print(f"       CRITICAL: {col} has {null_count:,} nulls ({description})")
        else:
            print(f"       PASSED: {col} - no nulls")

    # =========================================================================
    # CHECK 3: Null Values in Important Columns (Tier 2)
    # =========================================================================
    print("\n[3/6] Checking Tier 2 columns (Important - nulls not expected)...")

    tier2_columns = [
        ('perceived_stress_score', 'Key actionable predictor'),
        ('self_reported_happiness', 'Positive engagement predictor'),
        ('age', 'Demographic segmentation'),
    ]

    for col, description in tier2_columns:
        result = client.query(
            query=f"SELECT COUNT(*) - COUNT({col}) as null_count FROM {fq_table}",
            ref=branch_name
        )
        null_count = result.column("null_count")[0].as_py()
        null_summary[col] = null_count

        if null_count > 0:
            pct = (null_count / row_count) * 100
            if pct > 5:  # More than 5% nulls is critical
                critical_failures.append(f"{col}: {null_count:,} nulls ({pct:.1f}%)")
                print(f"       CRITICAL: {col} has {null_count:,} nulls ({pct:.1f}%) - {description}")
            else:
                warnings.append(f"{col}: {null_count:,} nulls ({pct:.1f}%)")
                print(f"       WARNING: {col} has {null_count:,} nulls ({pct:.1f}%) - {description}")
        else:
            print(f"       PASSED: {col} - no nulls")

    # =========================================================================
    # CHECK 4: Null Values in Platform Metrics (Tier 3)
    # =========================================================================
    print("\n[4/6] Checking Tier 3 columns (Recommended - platform metrics)...")

    tier3_columns = [
        'daily_active_minutes_instagram',
        'sessions_per_day',
        'followers_count',
        'following_count',
    ]

    for col in tier3_columns:
        result = client.query(
            query=f"SELECT COUNT(*) - COUNT({col}) as null_count FROM {fq_table}",
            ref=branch_name
        )
        null_count = result.column("null_count")[0].as_py()
        null_summary[col] = null_count

        if null_count > 0:
            pct = (null_count / row_count) * 100
            warnings.append(f"{col}: {null_count:,} nulls ({pct:.1f}%)")
            print(f"       WARNING: {col} has {null_count:,} nulls ({pct:.1f}%)")
        else:
            print(f"       PASSED: {col} - no nulls")

    # =========================================================================
    # CHECK 5: Value Range Validations
    # =========================================================================
    print("\n[5/6] Checking value ranges...")

    range_checks = [
        ('user_engagement_score', 0, 10, 'Engagement score'),
        ('age', 13, 120, 'User age'),
        ('perceived_stress_score', 0, 40, 'Stress score (PSS-10 scale)'),
        ('self_reported_happiness', 1, 10, 'Happiness score'),
    ]

    for col, min_val, max_val, description in range_checks:
        result = client.query(
            query=f"SELECT MIN({col}) as min_v, MAX({col}) as max_v FROM {fq_table}",
            ref=branch_name
        )
        actual_min = result.column("min_v")[0].as_py()
        actual_max = result.column("max_v")[0].as_py()

        if actual_min is not None and actual_max is not None:
            if actual_min < min_val or actual_max > max_val:
                critical_failures.append(
                    f"{col}: out of range [{min_val}, {max_val}], "
                    f"found [{actual_min}, {actual_max}]"
                )
                print(f"       CRITICAL: {col} out of range - expected [{min_val}, {max_val}], "
                      f"found [{actual_min}, {actual_max}]")
            else:
                print(f"       PASSED: {col} in range [{actual_min}, {actual_max}]")

    # =========================================================================
    # CHECK 6: Negative Value Checks
    # =========================================================================
    print("\n[6/6] Checking for negative values in count/time metrics...")

    non_negative_columns = [
        'time_on_feed_per_day',
        'time_on_reels_per_day',
        'daily_active_minutes_instagram',
        'sessions_per_day',
        'followers_count',
        'likes_given_per_day',
    ]

    for col in non_negative_columns:
        result = client.query(
            query=f"SELECT COUNT(*) as neg_count FROM {fq_table} WHERE {col} < 0",
            ref=branch_name
        )
        neg_count = result.column("neg_count")[0].as_py()

        if neg_count > 0:
            critical_failures.append(f"{col}: {neg_count:,} negative values")
            print(f"       CRITICAL: {col} has {neg_count:,} negative values")
        else:
            print(f"       PASSED: {col} - no negative values")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    total_checks = (
        1 +  # Row count
        len(tier1_columns) +
        len(tier2_columns) +
        len(tier3_columns) +
        len(range_checks) +
        len(non_negative_columns)
    )
    failed_checks = len(critical_failures)
    passed_checks = total_checks - failed_checks

    print("\n" + "=" * 60)
    print("DATA QUALITY SUMMARY")
    print("=" * 60)
    print(f"Total checks:    {total_checks}")
    print(f"Passed:          {passed_checks}")
    print(f"Failed:          {failed_checks}")
    print(f"Warnings:        {len(warnings)}")

    if critical_failures:
        print(f"\nCRITICAL FAILURES ({len(critical_failures)}):")
        for failure in critical_failures:
            print(f"  - {failure}")

    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")

    passed = len(critical_failures) == 0
    print(f"\nOVERALL STATUS: {'PASSED' if passed else 'FAILED'}")
    print("=" * 60)

    return DataQualityResult(
        passed=passed,
        total_checks=total_checks,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        critical_failures=critical_failures,
        warnings=warnings,
        row_count=row_count,
        null_summary=null_summary,
    )


def wap_ingest(
    table_name: str,
    s3_path: str,
    namespace: str = "bauplan",
    on_success: str = "inspect",
    on_failure: str = "keep",
    min_rows: int = 100_000,
    strict_quality: bool = True,
) -> tuple[str, bool, Optional[DataQualityResult]]:
    """
    Write-Audit-Publish flow for safe data ingestion with quality checks.

    Args:
        table_name: Target table name
        s3_path: S3 URI pattern for source data
        namespace: Target namespace
        on_success: "inspect" to keep branch for review, "merge" to auto-merge
        on_failure: "keep" to preserve branch for debugging, "delete" to cleanup
        min_rows: Minimum expected row count for validation
        strict_quality: If True, fail on any data quality issue

    Returns:
        tuple: (branch_name, success, data_quality_result)
    """
    client = bauplan.Client()

    # Generate unique branch name using username
    info = client.info()
    username = info.user.username
    branch_name = f"{username}.wap_{table_name}_{int(datetime.now().timestamp())}"

    success = False
    quality_result = None

    try:
        # === WRITE PHASE ===
        print("\n" + "=" * 60)
        print("WRITE PHASE")
        print("=" * 60)

        # 1. Create temporary branch from main
        assert not client.has_branch(branch_name), (
            f"Branch '{branch_name}' already exists - this should be an ephemeral branch"
        )
        client.create_branch(branch_name, from_ref="main")
        print(f"Created branch: {branch_name}")

        # 2. Create namespace if it doesn't exist
        try:
            client.create_namespace(namespace=namespace, branch=branch_name)
            print(f"Created namespace: {namespace}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"Namespace '{namespace}' already exists")
            else:
                raise

        # 3. Verify table doesn't exist on branch before creating
        if client.has_table(table=table_name, ref=branch_name, namespace=namespace):
            raise AssertionError(
                f"Table '{namespace}.{table_name}' already exists on branch"
            )

        # 4. Create table (schema inferred from S3 files)
        print(f"Creating table {namespace}.{table_name} from {s3_path}...")
        client.create_table(
            table=table_name,
            search_uri=s3_path,
            namespace=namespace,
            branch=branch_name,
        )

        # 5. Import data into table
        print("Importing data...")
        client.import_data(
            table=table_name,
            search_uri=s3_path,
            namespace=namespace,
            branch=branch_name,
        )
        print("Data import complete.")

        # === AUDIT PHASE ===
        quality_result = run_data_quality_checks(
            client=client,
            table_name=table_name,
            namespace=namespace,
            branch_name=branch_name,
            min_rows=min_rows,
        )

        # Check if quality passed
        if strict_quality and not quality_result.passed:
            raise AssertionError(
                f"Data quality validation failed with {quality_result.failed_checks} critical issues. "
                "Set strict_quality=False to proceed with warnings."
            )

        success = True

        # === PUBLISH PHASE ===
        print("\n" + "=" * 60)
        print("PUBLISH PHASE")
        print("=" * 60)

        if on_success == "merge":
            client.merge_branch(source_ref=branch_name, into_branch="main")
            print(f"Successfully published {table_name} to main")
            client.delete_branch(branch_name)
            print(f"Cleaned up branch: {branch_name}")
        else:
            print(f"Branch '{branch_name}' ready for inspection.")
            print(f"\nTo merge manually:")
            print(f"  bauplan checkout main")
            print(f"  bauplan branch merge {branch_name}")

    except Exception as e:
        print(f"\nWAP failed: {e}")
        if on_failure == "delete":
            if client.has_branch(branch_name):
                client.delete_branch(branch_name)
                print(f"Cleaned up failed branch: {branch_name}")
        else:
            print(f"Branch '{branch_name}' preserved for inspection/debugging.")
        raise

    return branch_name, success, quality_result


if __name__ == "__main__":
    branch, success, quality = wap_ingest(
        table_name="social_media_data",
        s3_path="s3://alpha-hello-bauplan/social-media-user-analysis/instagram_usage_lifestyle.csv",
        namespace="social",
        on_success="inspect",
        on_failure="keep",
        min_rows=100_000,
        strict_quality=True,
    )

    if quality:
        print(f"\nData Quality Score: {quality.passed_checks}/{quality.total_checks} checks passed")
