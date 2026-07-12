"""
Safe ingestion for ecommerce_sessions_week.
Write-Audit-Publish (WAP): import on an isolated branch, validate, then STOP (inspect).
The branch is kept OPEN for the downstream pipeline + dashboard work. It never merges to
main here — publishing to main happens via the reviewed GitHub PR (see README.md).
"""
import sys
import time

import bauplan

TABLE_NAME = "ecommerce_sessions_week"
S3_PATH = "s3://alpha-hello-bauplan/ecommerce-open-cdp/ecommerce_sessions_week.parquet"
NAMESPACE = "bauplan"


def validate_import(client, table_name, branch, namespace="bauplan"):
    """Minimal gate: table must be non-empty. Full checks live in expectations.py."""
    fq_table = f"{namespace}.{table_name}"
    result = client.query(f"SELECT COUNT(*) AS n FROM {fq_table}", ref=branch)
    row_count = result.column("n")[0].as_py()
    assert row_count > 0, f"{fq_table} has 0 rows after import"
    print(f"  Row count: {row_count}")
    return row_count


def main():
    client = bauplan.Client()
    username = client.info().user.username
    timestamp = int(time.time())
    branch_name = f"{username}.sessions_week_conv_{timestamp}"

    print(f"Creating branch: {branch_name}")
    client.create_branch(branch=branch_name, from_ref="main")

    try:
        print(f"\nPhase 1: Creating table '{TABLE_NAME}' from S3...")
        client.create_table(
            table=TABLE_NAME,
            search_uri=S3_PATH,
            branch=branch_name,
            namespace=NAMESPACE,
            replace=True,
        )
        print("  Table schema created.")

        print("  Importing data...")
        import_state = client.import_data(
            table=TABLE_NAME,
            search_uri=S3_PATH,
            branch=branch_name,
            namespace=NAMESPACE,
        )
        if import_state.error:
            raise RuntimeError(f"import_data failed: {import_state.error}")
        print("  Data imported.")

        print("\nPhase 2: Running minimal quality gate...")
        validate_import(client, TABLE_NAME, branch_name, NAMESPACE)

        print(f"\nSUCCESS. Branch ready for inspection (NOT merged): {branch_name}")
        print(f"BRANCH_NAME={branch_name}")

    except Exception as exc:
        print(f"\nImport FAILED: {exc}")
        print(f"Branch preserved for debugging: {branch_name}")
        print(f"BRANCH_NAME={branch_name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
