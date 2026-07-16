"""
Safe ingestion (Write-Audit-Publish) for the weekly ecommerce session export.

Loads the fresh session parquet from S3 onto an ISOLATED branch, validates it,
and leaves the branch open for review. It never merges to `main` — publishing
happens only when a human merges the review PR.

Standalone, re-runnable script (idempotent branch creation). This is NOT a
Bauplan model, so `bauplan run` will not pick it up — execute it directly:

    .venv/bin/python conversion-pipeline/ingestion.py
"""
import sys

import bauplan

TABLE_NAME = "ecommerce_sessions_week"
S3_PATH = "s3://alpha-hello-bauplan/ecommerce-open-cdp/ecommerce_sessions_week.parquet"
NAMESPACE = "bauplan"
BRANCH_NAME = "ciro.q4-reengagement-0716"
FROM_REF = "main"


def validate_import(client, table_name, branch, namespace=NAMESPACE):
    """Audit phase: sanity-check the raw import before it is eligible to publish.

    Raw session export — gate on non-empty. The full quality gate
    (segment domain, conversion bounds, non-null) runs on the pipeline output
    via the pipeline's expectations, not here.
    """
    fq_table = f"{namespace}.{table_name}"
    result = client.query(f"SELECT COUNT(*) AS n FROM {fq_table}", ref=branch)
    row_count = result.column("n")[0].as_py()
    assert row_count > 0, f"{fq_table} has 0 rows after import"
    print(f"  Row count: {row_count:,}")
    return row_count


def main():
    client = bauplan.Client()

    if client.has_branch(BRANCH_NAME):
        print(f"Branch already exists, reusing: {BRANCH_NAME}")
    else:
        print(f"Creating branch: {BRANCH_NAME} (from {FROM_REF})")
        client.create_branch(branch=BRANCH_NAME, from_ref=FROM_REF)

    try:
        # === IMPORT PHASE (Write) ===
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

        # === VALIDATION PHASE (Audit) ===
        print("\nPhase 2: Running quality checks...")
        validate_import(client, TABLE_NAME, BRANCH_NAME, NAMESPACE)

        # === PUBLISH PHASE — intentionally NOT automated ===
        # Never merge to main here. The branch stays open for review; a human
        # merges the review PR to publish.
        print(f"\nImport complete. Branch ready for review: '{BRANCH_NAME}'")
        print(
            f'  Query:  bauplan query "SELECT * FROM {NAMESPACE}.{TABLE_NAME} LIMIT 10" '
            f"--ref {BRANCH_NAME}"
        )

    except Exception as exc:
        print(f"\nImport FAILED: {exc}")
        print(f"Branch preserved for debugging: '{BRANCH_NAME}'")
        sys.exit(1)


if __name__ == "__main__":
    main()
