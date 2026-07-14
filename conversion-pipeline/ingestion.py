"""
Safe ingestion (WAP) for this week's ecommerce sessions.

Write-Audit-Publish: import onto an isolated branch, validate, then leave the
branch open for review. This script NEVER merges to `main` — publishing happens
only when a human merges the review PR.

Re-runnable: creates the branch from `main` if it does not already exist, and
replaces the table on each run so the import is idempotent.

    .venv/bin/python conversion-pipeline/ingestion.py
"""
import sys
import bauplan


TABLE_NAME = "ecommerce_sessions_week"
S3_PATH = "s3://alpha-hello-bauplan/ecommerce-open-cdp/ecommerce_sessions_week.parquet"
NAMESPACE = "bauplan"
BRANCH_NAME = "ciro.q4-reengagement"


def validate_import(client, table_name, branch, namespace="bauplan"):
    """Minimal gate: the imported table must be non-empty."""
    fq_table = f"{namespace}.{table_name}"
    result = client.query(f"SELECT COUNT(*) AS n FROM {fq_table}", ref=branch)
    row_count = result.column("n")[0].as_py()
    assert row_count > 0, f"{fq_table} has 0 rows after import"
    print(f"  Row count: {row_count}")


def main():
    client = bauplan.Client()

    if not client.has_branch(BRANCH_NAME):
        print(f"Creating branch: {BRANCH_NAME}")
        client.create_branch(branch=BRANCH_NAME, from_ref="main")
    else:
        print(f"Reusing existing branch: {BRANCH_NAME}")

    try:
        # === IMPORT PHASE ===
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

        # === VALIDATION PHASE ===
        print("\nPhase 2: Running quality checks...")
        validate_import(client, TABLE_NAME, BRANCH_NAME, NAMESPACE)

        # === INSPECT (no merge) ===
        print(f"\nImport complete. Branch ready for review: '{BRANCH_NAME}'")
        print(
            f'To query:  bauplan query "SELECT * FROM {NAMESPACE}.{TABLE_NAME} LIMIT 10" '
            f"--ref {BRANCH_NAME}"
        )
        print(f"To merge:  bauplan branch merge {BRANCH_NAME} --into main  (humans only)")

    except Exception as exc:
        print(f"\nImport FAILED: {exc}")
        print(f"Branch preserved for debugging: '{BRANCH_NAME}'")
        sys.exit(1)


if __name__ == "__main__":
    main()
