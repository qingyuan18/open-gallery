#!/usr/bin/env python3
"""
Database version switching script for Jaaz
Allows switching between different database backend versions
"""
import sys
import os
import argparse

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.migrations.manager import MigrationManager
from services.migrations.v5_dynamodb_legacy_schema import V5DynamoDBLegacySchema
from services.migrations.v6_dynamodb_multitenant_schema import V6DynamoDBMultitenantSchema


def show_available_versions():
    """Show available database versions"""
    print("""
🗄️ Available Database Versions:

Version 1-4: SQLite Database (Legacy)
  - v1: Initial schema (chat_sessions, chat_messages)
  - v2: Add canvases table
  - v3: Add comfy_workflows table  
  - v4: Add files table

Version 5: DynamoDB Legacy Schema
  - Single-tenant DynamoDB tables
  - No user_id fields
  - Compatible with old application code
  - Tables: canvases, chat_sessions, chat_messages, comfy_workflows, files

Version 6: DynamoDB Multi-tenant Schema
  - Multi-tenant DynamoDB tables
  - All tables include user_id fields
  - User authentication and isolation
  - Tables: canvases, chat_sessions, chat_messages, comfy_workflows, files, users
  - Default users: admin/admin123, demo/demo123

Recommended:
  - New installations: Use version 6 (multi-tenant)
  - Existing SQLite users: Migrate to version 6
  - Legacy compatibility: Use version 5
""")


def switch_to_version_5():
    """Switch to DynamoDB legacy schema (version 5)"""
    print("🔄 Switching to DynamoDB Legacy Schema (Version 5)...")
    
    try:
        migration = V5DynamoDBLegacySchema()
        migration.up(None)  # DynamoDB migrations don't use SQLite connection
        print("✅ Successfully switched to DynamoDB Legacy Schema (Version 5)")
        print("""
📋 Version 5 Features:
  - DynamoDB backend
  - Single-tenant (no user isolation)
  - Compatible with old application code
  - No authentication required
  
⚠️ Note: This version does not support user authentication or multi-tenancy.
""")
        return True
        
    except Exception as e:
        print(f"❌ Failed to switch to version 5: {e}")
        import traceback
        traceback.print_exc()
        return False


def switch_to_version_6():
    """Switch to DynamoDB multi-tenant schema (version 6)"""
    print("🔄 Switching to DynamoDB Multi-tenant Schema (Version 6)...")
    
    try:
        migration = V6DynamoDBMultitenantSchema()
        migration.up(None)  # DynamoDB migrations don't use SQLite connection
        print("✅ Successfully switched to DynamoDB Multi-tenant Schema (Version 6)")
        print("""
📋 Version 6 Features:
  - DynamoDB backend
  - Multi-tenant with user isolation
  - User authentication system
  - Default users created:
    * admin / admin123
    * demo / demo123
  
🔐 Authentication: All API endpoints require valid JWT tokens.
""")
        return True
        
    except Exception as e:
        print(f"❌ Failed to switch to version 6: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_version_5():
    """Clean up DynamoDB legacy schema"""
    print("🗑️ Cleaning up DynamoDB Legacy Schema (Version 5)...")
    
    try:
        migration = V5DynamoDBLegacySchema()
        migration.down(None)
        print("✅ Successfully cleaned up DynamoDB Legacy Schema")
        return True
        
    except Exception as e:
        print(f"❌ Failed to cleanup version 5: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_version_6():
    """Clean up DynamoDB multi-tenant schema"""
    print("🗑️ Cleaning up DynamoDB Multi-tenant Schema (Version 6)...")
    
    try:
        migration = V6DynamoDBMultitenantSchema()
        migration.down(None)
        print("✅ Successfully cleaned up DynamoDB Multi-tenant Schema")
        return True
        
    except Exception as e:
        print(f"❌ Failed to cleanup version 6: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_aws_credentials():
    """Verify AWS credentials are configured"""
    try:
        import boto3
        # Try to create a DynamoDB client
        client = boto3.client('dynamodb', region_name='us-west-2')
        # Try to list tables (this will fail if credentials are not configured)
        client.list_tables()
        print("✅ AWS credentials are configured")
        return True
    except Exception as e:
        print(f"❌ AWS credentials not configured or invalid: {e}")
        print("""
🔧 To configure AWS credentials, you can:
1. Set environment variables:
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   export AWS_DEFAULT_REGION=us-west-2

2. Use AWS CLI:
   aws configure

3. Use IAM roles (for EC2 instances)

4. Use AWS credentials file (~/.aws/credentials)
""")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Switch between different database backend versions for Jaaz",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'action',
        choices=['list', 'switch', 'cleanup', 'verify'],
        help='Action to perform'
    )
    
    parser.add_argument(
        '--version',
        type=int,
        choices=[5, 6],
        help='Database version to switch to (5 or 6)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force operation without confirmation'
    )
    
    args = parser.parse_args()
    
    if args.action == 'list':
        show_available_versions()
        return
    
    if args.action == 'verify':
        verify_aws_credentials()
        return
    
    if args.action in ['switch', 'cleanup'] and not args.version:
        print("❌ --version is required for switch and cleanup actions")
        parser.print_help()
        return
    
    # Verify AWS credentials for DynamoDB operations
    if args.version in [5, 6] and not verify_aws_credentials():
        print("❌ Cannot proceed without valid AWS credentials")
        return
    
    if args.action == 'switch':
        if not args.force:
            print(f"⚠️ This will create/modify DynamoDB tables for version {args.version}")
            confirm = input("Continue? (y/N): ").lower().strip()
            if confirm != 'y':
                print("Operation cancelled")
                return
        
        if args.version == 5:
            success = switch_to_version_5()
        elif args.version == 6:
            success = switch_to_version_6()
        
        if success:
            print(f"\n🎉 Successfully switched to database version {args.version}")
        else:
            print(f"\n❌ Failed to switch to database version {args.version}")
            sys.exit(1)
    
    elif args.action == 'cleanup':
        if not args.force:
            print(f"⚠️ This will DELETE all DynamoDB tables for version {args.version}")
            print("⚠️ ALL DATA WILL BE LOST!")
            confirm = input("Are you sure? Type 'DELETE' to confirm: ").strip()
            if confirm != 'DELETE':
                print("Operation cancelled")
                return
        
        if args.version == 5:
            success = cleanup_version_5()
        elif args.version == 6:
            success = cleanup_version_6()
        
        if success:
            print(f"\n🎉 Successfully cleaned up database version {args.version}")
        else:
            print(f"\n❌ Failed to cleanup database version {args.version}")
            sys.exit(1)


if __name__ == "__main__":
    main()
