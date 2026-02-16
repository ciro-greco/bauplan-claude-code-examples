"""
run_flow.py
=================

Demo script that runs a full import + pipeline flow on Bauplan.

Usage:
    python run_flow.py --no-plan   # import with original schema from S3
    python run_flow.py --plan      # import with schema override (cast trip_miles to STRING)
"""

import argparse
import bauplan
from datetime import datetime, timezone

# ── Configuration ──────────────────────────────────────────────────
S3_URI = "s3://alpha-hello-bauplan/taxi_fhvhv_2021/*.parquet"
TABLE_NAME = "taxi_trips_2021"
NAMESPACE = "bauplan"
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
BRANCH_NAME = f"ciro.import_{TIMESTAMP}"
TARGET_COLUMN = "trip_miles"
TARGET_TYPE = "string"


def main():
    parser = argparse.ArgumentParser(description="Run Bauplan import + pipeline flow.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", action="store_true", help="Override trip_miles type to STRING before import")
    group.add_argument("--no-plan", action="store_true", help="Import with original schema from S3")
    args = parser.parse_args()

    override_schema = args.plan

    client = bauplan.Client()

    # ── 1. Create an isolated branch ──────────────────────────────
    print("\n═══ Step 1: Create branch for the import ═══")
    client.create_branch(branch=BRANCH_NAME, from_ref="main")
    print(f"   Created branch: {BRANCH_NAME}")

    # ── 2. Generate the import plan ───────────────────────────────
    print("\n═══ Step 2: Generate create-plan from S3 ═══")
    plan_state = client.plan_table_creation(
        table=TABLE_NAME,
        search_uri=S3_URI,
        branch=BRANCH_NAME,
        namespace=NAMESPACE,
        replace=True,
    )
    print(f"   Plan created for {NAMESPACE}.{TABLE_NAME}")

    # ── 3. Optionally override schema ─────────────────────────────
    if override_schema:
        print("\n═══ Step 3: Override schema — casting trip_miles to STRING ═══")
        for col in plan_state.plan["schema_info"]["detected_schemas"]:
            if col["column_name"] == TARGET_COLUMN:
                original = col["dst_datatype"]
                col["dst_datatype"] = [{"datatype": TARGET_TYPE}]
                print(f"   {TARGET_COLUMN}: {original} -> {col['dst_datatype']}")
                break
    else:
        print("\n═══ Step 3: Skipped — using original schema ═══")

    # ── 4. Apply the table creation plan ────────────────────────────
    print("\n═══ Step 4: Create table with the plan ═══")
    create_state = client.apply_table_creation_plan(plan=plan_state)
    print(f"   Table creation finished (job_id: {create_state.job_id})")
    print(f"   Job status: {create_state.job_status}")

    if create_state.job_status != "SUCCESS":
        print(f"\n   Table creation FAILED on branch {BRANCH_NAME}")
        if create_state.error:
            print(f"   Error: {create_state.error}")
        return

    # ── 5. Import data into the table ─────────────────────────────
    print("\n═══ Step 5: Import data from S3 ═══")
    import_state = client.import_data(
        table=TABLE_NAME,
        search_uri=S3_URI,
        branch=BRANCH_NAME,
        namespace=NAMESPACE,
    )
    print(f"   Data import finished (job_id: {import_state.job_id})")
    print(f"   Job status: {import_state.job_status}")

    if import_state.job_status != "SUCCESS":
        print(f"\n   Data import FAILED on branch {BRANCH_NAME}")
        if import_state.error:
            print(f"   Error: {import_state.error}")
        return

    # ── 6. Verify the schema ────────────────────────────────────────
    print("\n═══ Step 6: Verify trip_miles type ═══")
    table_meta = client.get_table(
        table=TABLE_NAME,
        ref=BRANCH_NAME,
        namespace=NAMESPACE,
    )
    for field in table_meta.fields:
        if field.name == TARGET_COLUMN:
            print(f"   {field.name}: {field.type}")
            break
    print(f"   Import on {BRANCH_NAME} completed.")

    # ── 7. Run Transformation Pipeline ───────────────────────────────
    print(f"\n═══ Step 7: Running transformation pipeline on {BRANCH_NAME}...")

    run_state = client.run(project_dir='pipeline', ref=BRANCH_NAME)
    print(f"   Pipeline run finished (job_id: {run_state.job_id})")
    print(f"   Job status: {run_state.job_status}")

    if run_state.job_status != "SUCCESS":
        print(f"\n   Pipeline run FAILED on branch {BRANCH_NAME}")
        if run_state.error:
            print(f"   Error: {run_state.error}")
        return

    print(f"\nDone. Check {BRANCH_NAME} before merging.")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()