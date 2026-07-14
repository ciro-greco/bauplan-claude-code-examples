"""
Safe ingestion (Write-Audit-Publish) for `bauplan.ecommerce_sessions_week`.

Loads this week's ecommerce session export from S3 onto an ISOLATED branch,
validates it, and stops before merging to `main`. The branch is left open for
review so the downstream conversion pipeline can be built on top of it and the
whole thing shipped in a single review PR.

Re-runnable: `python conversion-pipeline/ingestion.py`
This is a standalone WAP script, NOT a Bauplan model — `bauplan run` ignores it.
"""
import sys
import bauplan


TABLE_NAME = "ecommerce_sessions_week"
S3_PATH = "s3://alpha-hello-bauplan/ecommerce-open-cdp/ecommerce_sessions_week.parquet"
NAMESPACE = "bauplan"
BRANCH_NAME = "ciro.q4-reengagement"


def validate_import(client, table_name, branch, namespace=NAMESPACE):
    """Audit phase. Raises on FAIL so a bad import never reaches review."""
    fq_table = f"{namespace}.{table_name}"

    result = client.query(f"SELECT COUNT(*) AS n FROM {fq_table}", ref=branch)
    row_count = result.column("n")[0].as_py()
    assert row_count > 0, f"{fq_table} has 0 rows after import"
    print(f"  Row count: {row_count}")


def main():
    client = bauplan.Client()

    # Isolate: create the branch off main if it isn't there yet. Never import to main.
    if not client.has_branch(BRANCH_NAME):
        print(f"Creating branch: {BRANCH_NAME}")
        client.create_branch(branch=BRANCH_NAME, from_ref="main")
    else:
        print(f"Reusing existing branch: {BRANCH_NAME}")

    try:
        # === WRITE ===
        print(f"\nPhase 1: Creating table '{TABLE_NAME}' from S3...")
        client.create_table(
            table=TABLE_NAME,
            search_uri=S3_PATH,
            branch=BRANCH_NAME,
            namespace=NAMESPACE,
            replace=True,
        )
        print("  Table schema created.")

        print("  Importing data...")
        import_state = client.import_data(
            table=TABLE_NAME,
            search_uri=S3_PATH,
            branch=BRANCH_NAME,
            namespace=NAMESPACE,
        )
        if import_state.error:
            raise RuntimeError(f"import_data failed: {import_state.error}")
        print("  Data imported.")

        # === AUDIT ===
        print("\nPhase 2: Running quality checks...")
        validate_import(client, TABLE_NAME, BRANCH_NAME, NAMESPACE)

        # === PUBLISH === intentionally NOT done here.
        # The branch stays open; publishing happens only when a human merges the review PR.
        print(f"\nImport complete. Branch open for review: '{BRANCH_NAME}'")
        print(
            f'To query:  bauplan query "SELECT * FROM {NAMESPACE}.{TABLE_NAME} LIMIT 10" --ref {BRANCH_NAME}'
        )

    except Exception as exc:
        print(f"\nImport FAILED: {exc}")
        print(f"Branch preserved for debugging: '{BRANCH_NAME}'")
        sys.exit(1)


if __name__ == "__main__":
    main()
