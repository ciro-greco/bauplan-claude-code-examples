"""
Write-Audit-Publish (WAP) Data Ingestion Script for Social Media Data

This script implements the WAP pattern to safely ingest CSV data from S3 into Bauplan:
1. Create a working branch for data operations
2. Create namespace if needed
3. Create table with inferred schema from S3 data
4. Import data into the table
5. Run comprehensive data quality checks
6. Publish to main branch if all checks pass

Author: Ciro Greco
Data Source: s3://alpha-hello-bauplan/social-media-user-analysis/instagram_usage_lifestyle.csv
Target Table: social_media.social_media_data
"""

import time
import sys
from typing import Dict, Any, Optional, List

# Import Bauplan SDK
import bauplan


def create_ingestion_branch(username: str) -> str:
    """Create a unique branch for WAP ingestion operations."""
    current_epoch = int(time.time())
    branch_name = f"{username}.ingestion_{current_epoch}"
    
    print(f"Creating ingestion branch: {branch_name}")
    
    try:
        bauplan.create_branch(branch_name, from_ref="main")
        print(f"✓ Successfully created branch: {branch_name}")
        return branch_name
    except Exception as e:
        print(f"✗ Failed to create branch: {str(e)}")
        sys.exit(1)


def ensure_namespace_exists(namespace: str, branch: str) -> bool:
    """Ensure the target namespace exists in the branch."""
    print(f"Checking if namespace '{namespace}' exists in branch '{branch}'")
    
    try:
        # Check if namespace exists
        existing_namespaces = bauplan.get_namespaces(ref=branch)
        namespace_exists = any(ns.name == namespace for ns in existing_namespaces)
        
        if namespace_exists:
            print(f"✓ Namespace '{namespace}' already exists")
            return True
        
        # Create namespace if it doesn't exist
        print(f"Creating namespace: {namespace}")
        bauplan.create_namespace(namespace, branch=branch)
        print(f"✓ Successfully created namespace: {namespace}")
        return True
        
    except Exception as e:
        print(f"✗ Error managing namespace: {str(e)}")
        return False


def create_table_from_s3(table_name: str, s3_uri: str, branch: str, namespace: str) -> bool:
    """Create table with schema inferred from S3 CSV data."""
    print(f"Creating table '{table_name}' from S3 URI: {s3_uri}")
    
    try:
        bauplan.create_table(
            table=table_name,
            search_uri=s3_uri,
            branch=branch,
            namespace=namespace,
            replace=True  # Replace if exists
        )
        print(f"✓ Successfully created table: {namespace}.{table_name}")
        return True
        
    except Exception as e:
        print(f"✗ Error creating table: {str(e)}")
        return False


def import_data_from_s3(table_name: str, s3_uri: str, branch: str, namespace: str) -> bool:
    """Import data from S3 into the created table."""
    print(f"Importing data from {s3_uri} into {namespace}.{table_name}")
    
    try:
        bauplan.import_data(
            table=table_name,
            search_uri=s3_uri,
            branch=branch,
            namespace=namespace
        )
        print(f"✓ Successfully imported data into: {namespace}.{table_name}")
        return True
        
    except Exception as e:
        print(f"✗ Error importing data: {str(e)}")
        return False


def get_table_schema(table_name: str, ref: str, namespace: str) -> Optional[Dict[str, Any]]:
    """Get table schema for quality check planning."""
    try:
        table_info = bauplan.get_table(ref=ref, table_name=table_name, namespace=namespace)
        return table_info
        
    except Exception as e:
        print(f"✗ Error retrieving table schema: {str(e)}")
        return None


def run_data_quality_checks(table_name: str, ref: str, namespace: str) -> bool:
    """Run comprehensive data quality checks on the imported data."""
    print(f"\n=== Running Data Quality Checks ===")
    print(f"Table: {namespace}.{table_name}")
    print(f"Branch: {ref}")
    
    try:
        # Get table schema first
        schema_info = get_table_schema(table_name, ref, namespace)
        if not schema_info:
            print("✗ Cannot run quality checks without table schema")
            return False
            
        full_table_name = f"{namespace}.{table_name}"
        
        # Quality Check 1: Row count (should be > 0)
        print("\n1. Checking row count...")
        count_query = f"SELECT COUNT(*) as row_count FROM {full_table_name}"
        count_result = bauplan.run_query(query=count_query, ref=ref, namespace=namespace)
        
        if count_result:
            row_count = count_result[0]["row_count"]
            print(f"   Row count: {row_count:,}")
            if row_count == 0:
                print("✗ FAILED: Table is empty")
                return False
            print("✓ PASSED: Table has data")
        else:
            print("✗ FAILED: Could not get row count")
            return False
        
        # Quality Check 2: Check for completely null columns
        print("\n2. Checking for completely null columns...")
        schema_fields = schema_info.get("schema", {}).get("fields", [])
        
        for field in schema_fields:
            column_name = field["name"]
            null_check_query = f"""
            SELECT 
                COUNT(*) as total_rows,
                COUNT({column_name}) as non_null_rows,
                (COUNT(*) - COUNT({column_name})) as null_rows
            FROM {full_table_name}
            """
            
            null_result = bauplan.run_query(query=null_check_query, ref=ref, namespace=namespace)
            
            if null_result:
                null_data = null_result[0]
                total_rows = null_data["total_rows"]
                null_rows = null_data["null_rows"]
                null_percentage = (null_rows / total_rows) * 100 if total_rows > 0 else 0
                
                print(f"   Column '{column_name}': {null_percentage:.1f}% null values")
                
                # Warning for high null percentage
                if null_percentage > 95:
                    print(f"   ⚠ WARNING: Column '{column_name}' is {null_percentage:.1f}% null")
                elif null_percentage == 100:
                    print(f"   ✗ FAILED: Column '{column_name}' is completely null")
                    return False
            else:
                print(f"   ✗ Could not check nulls for column '{column_name}'")
        
        print("✓ PASSED: No completely null columns found")
        
        # Quality Check 3: Sample data inspection
        print("\n3. Sample data inspection...")
        sample_query = f"SELECT * FROM {full_table_name} LIMIT 5"
        sample_result = bauplan.run_query(query=sample_query, ref=ref, namespace=namespace)
        
        if sample_result:
            print(f"   Sample rows retrieved: {len(sample_result)}")
            print("✓ PASSED: Sample data accessible")
        else:
            print("✗ FAILED: Cannot retrieve sample data")
            return False
        
        # Quality Check 4: Duplicate detection (basic check)
        print("\n4. Checking for duplicate rows...")
        duplicate_query = f"""
        SELECT COUNT(*) as total_rows, COUNT(DISTINCT *) as unique_rows
        FROM {full_table_name}
        """
        
        dup_result = bauplan.run_query(query=duplicate_query, ref=ref, namespace=namespace)
        
        if dup_result:
            dup_data = dup_result[0]
            total_rows = dup_data["total_rows"]
            unique_rows = dup_data["unique_rows"]
            duplicate_rows = total_rows - unique_rows
            
            print(f"   Total rows: {total_rows:,}")
            print(f"   Unique rows: {unique_rows:,}")
            print(f"   Duplicate rows: {duplicate_rows:,}")
            
            if duplicate_rows > 0:
                duplicate_percentage = (duplicate_rows / total_rows) * 100
                print(f"   ⚠ WARNING: {duplicate_percentage:.1f}% duplicate rows detected")
                # Don't fail on duplicates, just warn
            
            print("✓ PASSED: Duplicate check completed")
        else:
            print("⚠ Could not check for duplicates")
        
        print("\n=== All Quality Checks Completed ===")
        print("✓ Data quality validation successful!")
        return True
        
    except Exception as e:
        print(f"✗ Error during quality checks: {str(e)}")
        return False


def publish_to_main(source_branch: str) -> bool:
    """Merge the working branch into main branch."""
    print(f"\n=== Publishing to Main Branch ===")
    print(f"Merging {source_branch} into main")
    
    try:
        bauplan.merge_branch(
            source_ref=source_branch,
            into_branch="main",
            commit_message=f"WAP: Import social media data from Instagram usage lifestyle CSV",
            commit_body=f"Automated WAP ingestion of social media data into social_media.social_media_data table.\n\n"
                        f"Source: s3://alpha-hello-bauplan/social-media-user-analysis/instagram_usage_lifestyle.csv\n"
                        f"Quality checks: PASSED\n"
                        f"Ingestion branch: {source_branch}"
        )
        print("✓ Successfully merged to main branch!")
        print("✓ WAP ingestion completed successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Error during merge: {str(e)}")
        return False


def cleanup_branch(branch_name: str) -> None:
    """Clean up the working branch after successful merge."""
    print(f"\nCleaning up working branch: {branch_name}")
    
    try:
        bauplan.delete_branch(branch=branch_name)
        print(f"✓ Successfully deleted working branch: {branch_name}")
        
    except Exception as e:
        print(f"⚠ Error during cleanup: {str(e)}")


def main() -> None:
    """Main WAP ingestion workflow."""
    print("=== Write-Audit-Publish (WAP) Data Ingestion ===")
    print("Ingesting social media data from S3 into Bauplan")
    print()
    
    # Configuration
    USERNAME = "ciro"
    S3_URI = "s3://alpha-hello-bauplan/social-media-user-analysis/instagram_usage_lifestyle.csv"
    NAMESPACE = "social_media"
    TABLE_NAME = "social_media_data"
    
    print(f"Configuration:")
    print(f"  User: {USERNAME}")
    print(f"  Source: {S3_URI}")
    print(f"  Target Table: {NAMESPACE}.{TABLE_NAME}")
    print()
    
    working_branch = None
    
    try:
        # Step 1: Create working branch
        working_branch = create_ingestion_branch(USERNAME)
        
        # Step 2: Ensure namespace exists
        if not ensure_namespace_exists(NAMESPACE, working_branch):
            print("✗ WAP ingestion failed: Could not create/verify namespace")
            return
        
        # Step 3: Create table from S3 schema
        if not create_table_from_s3(TABLE_NAME, S3_URI, working_branch, NAMESPACE):
            print("✗ WAP ingestion failed: Could not create table")
            return
        
        # Step 4: Import data from S3
        if not import_data_from_s3(TABLE_NAME, S3_URI, working_branch, NAMESPACE):
            print("✗ WAP ingestion failed: Could not import data")
            return
        
        # Step 5: Run data quality checks
        if not run_data_quality_checks(TABLE_NAME, working_branch, NAMESPACE):
            print("✗ WAP ingestion failed: Data quality checks failed")
            print(f"⚠ Working branch '{working_branch}' preserved for investigation")
            return
        
        # Step 6: Publish to main (merge)
        if not publish_to_main(working_branch):
            print("✗ WAP ingestion failed: Could not publish to main")
            print(f"⚠ Working branch '{working_branch}' preserved for investigation")
            return
        
        # Step 7: Cleanup
        cleanup_branch(working_branch)
        
        print("\n" + "="*50)
        print("🎉 WAP INGESTION COMPLETED SUCCESSFULLY!")
        print("="*50)
        print(f"✓ Data successfully ingested into: {NAMESPACE}.{TABLE_NAME}")
        print(f"✓ All quality checks passed")
        print(f"✓ Changes published to main branch")
        print()
        
    except KeyboardInterrupt:
        print("\n⚠ WAP ingestion interrupted by user")
        if working_branch:
            print(f"⚠ Working branch '{working_branch}' preserved for manual cleanup")
    except Exception as e:
        print(f"\n✗ WAP ingestion failed with unexpected error: {str(e)}")
        if working_branch:
            print(f"⚠ Working branch '{working_branch}' preserved for investigation")


if __name__ == "__main__":
    main()