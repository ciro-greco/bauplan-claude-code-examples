"""
WAP (Write-Audit-Publish) script for social media data ingestion.

Imports data from S3 into the bauplan lakehouse using the WAP pattern
for safe data loading with quality checks.
"""

import bauplan
from datetime import datetime


def wap_ingest(
    table_name: str,
    s3_path: str,
    namespace: str = "bauplan",
    on_success: str = "inspect",
    on_failure: str = "keep",
) -> tuple[str, bool]:
    """
    Write-Audit-Publish flow for safe data ingestion.

    Args:
        table_name: Target table name
        s3_path: S3 URI pattern for source data
        namespace: Target namespace
        on_success: "inspect" to keep branch for review, "merge" to auto-merge
        on_failure: "keep" to preserve branch for debugging, "delete" to cleanup

    Returns:
        tuple: (branch_name, success)
    """
    client = bauplan.Client()

    # Generate unique branch name using username
    info = client.info()
    username = info.user.username
    branch_name = f"{username}.wap_{table_name}_{int(datetime.now().timestamp())}"

    success = False
    try:
        # === WRITE PHASE ===
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
                f"Table '{namespace}.{table_name}' already exists on branch - refusing to overwrite"
            )

        # 4. Create table (schema inferred from S3 files)
        print(f"Creating table {namespace}.{table_name} from {s3_path}...")
        client.create_table(
            table=table_name,
            search_uri=s3_path,
            namespace=namespace,
            branch=branch_name,
        )

        # 4. Import data into table
        print("Importing data...")
        client.import_data(
            table=table_name,
            search_uri=s3_path,
            namespace=namespace,
            branch=branch_name,
        )

        # === AUDIT PHASE ===
        # 5. Run quality check: verify data was imported
        fq_table = f"{namespace}.{table_name}"
        result = client.query(
            query=f"SELECT COUNT(*) as row_count FROM {fq_table}", ref=branch_name
        )
        row_count = result.column("row_count")[0].as_py()
        assert row_count > 0, "No data was imported"
        print(f"Imported {row_count} rows")

        success = True

        # === PUBLISH PHASE ===
        if on_success == "merge":
            # Merge to main and cleanup
            client.merge_branch(source_ref=branch_name, into_branch="main")
            print(f"Successfully published {table_name} to main")
            client.delete_branch(branch_name)
            print(f"Cleaned up branch: {branch_name}")
        else:
            # Keep branch for inspection
            print(
                f"\nWAP completed successfully. Branch '{branch_name}' ready for inspection."
            )
            print(
                f"To merge manually: client.merge_branch(source_ref='{branch_name}', into_branch='main')"
            )

    except Exception as e:
        print(f"WAP failed: {e}")
        if on_failure == "delete":
            if client.has_branch(branch_name):
                client.delete_branch(branch_name)
                print(f"Cleaned up failed branch: {branch_name}")
        else:
            print(f"Branch '{branch_name}' preserved for inspection/debugging.")
        raise

    return branch_name, success


if __name__ == "__main__":
    branch, success = wap_ingest(
        table_name="social_media_data",
        s3_path="s3://alpha-hello-bauplan/social-media-user-analysis/instagram_usage_lifestyle.csv",
        namespace="social",
        on_success="inspect",
        on_failure="keep",
    )
