#!/usr/bin/env python3
"""
Fix missing DynamoDB indexes for multi-tenant support
"""
import sys
import os
import boto3
from botocore.exceptions import ClientError
import time

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def wait_for_table_active(dynamodb, table_name):
    """Wait for table to become active"""
    print(f"⏳ Waiting for table {table_name} to become active...")
    waiter = dynamodb.meta.client.get_waiter('table_exists')
    waiter.wait(TableName=table_name)
    
    table = dynamodb.Table(table_name)
    while table.table_status != 'ACTIVE':
        print(f"   Table status: {table.table_status}")
        time.sleep(5)
        table.reload()
    print(f"✅ Table {table_name} is active")

def add_index_if_not_exists(dynamodb, table_name, index_name, key_schema, attribute_definitions):
    """Add global secondary index if it doesn't exist"""
    try:
        table = dynamodb.Table(table_name)
        
        # Check if index already exists
        existing_indexes = table.global_secondary_indexes or []
        for index in existing_indexes:
            if index['IndexName'] == index_name:
                print(f"✅ Index {index_name} already exists on {table_name}")
                return True
        
        print(f"🔧 Adding index {index_name} to table {table_name}...")
        
        # Add the index
        table.meta.client.update_table(
            TableName=table_name,
            AttributeDefinitions=attribute_definitions,
            GlobalSecondaryIndexUpdates=[
                {
                    'Create': {
                        'IndexName': index_name,
                        'KeySchema': key_schema,
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                }
            ]
        )
        
        # Wait for index to be created
        print(f"⏳ Waiting for index {index_name} to be created...")
        waiter = dynamodb.meta.client.get_waiter('table_exists')
        waiter.wait(TableName=table_name)
        
        # Wait for table to be active again
        wait_for_table_active(dynamodb, table_name)
        
        print(f"✅ Index {index_name} created successfully")
        return True
        
    except ClientError as e:
        if 'ResourceInUseException' in str(e):
            print(f"⏳ Table {table_name} is being updated, waiting...")
            time.sleep(30)
            return add_index_if_not_exists(dynamodb, table_name, index_name, key_schema, attribute_definitions)
        else:
            print(f"❌ Failed to add index {index_name}: {e}")
            return False
    except Exception as e:
        print(f"❌ Error adding index {index_name}: {e}")
        return False

def fix_canvases_table(dynamodb):
    """Fix canvases table indexes"""
    print("\n🎨 Fixing canvases table indexes...")
    
    table_name = 'jaaz-canvases'
    
    # Add user_id-updated_at-index
    success1 = add_index_if_not_exists(
        dynamodb, table_name, 'user_id-updated_at-index',
        key_schema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
        ],
        attribute_definitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'updated_at', 'AttributeType': 'S'}
        ]
    )
    
    return success1

def fix_chat_sessions_table(dynamodb):
    """Fix chat_sessions table indexes"""
    print("\n💬 Fixing chat_sessions table indexes...")
    
    table_name = 'jaaz-chat-sessions'
    
    # Add user_id-updated_at-index
    success1 = add_index_if_not_exists(
        dynamodb, table_name, 'user_id-updated_at-index',
        key_schema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
        ],
        attribute_definitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'updated_at', 'AttributeType': 'S'}
        ]
    )
    
    return success1

def fix_chat_messages_table(dynamodb):
    """Fix chat_messages table indexes"""
    print("\n📝 Fixing chat_messages table indexes...")
    
    table_name = 'jaaz-chat-messages'
    
    # Add user_id-session_id-index
    success1 = add_index_if_not_exists(
        dynamodb, table_name, 'user_id-session_id-index',
        key_schema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
            {'AttributeName': 'session_id', 'KeyType': 'RANGE'}
        ],
        attribute_definitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'session_id', 'AttributeType': 'S'}
        ]
    )
    
    return success1

def fix_files_table(dynamodb):
    """Fix files table indexes"""
    print("\n📁 Fixing files table indexes...")
    
    table_name = 'jaaz-files'
    
    # Add user_id-created_at-index
    success1 = add_index_if_not_exists(
        dynamodb, table_name, 'user_id-created_at-index',
        key_schema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
            {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
        ],
        attribute_definitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'created_at', 'AttributeType': 'S'}
        ]
    )
    
    return success1

def fix_workflows_table(dynamodb):
    """Fix comfy_workflows table indexes"""
    print("\n🔄 Fixing comfy_workflows table indexes...")
    
    table_name = 'jaaz-comfy-workflows'
    
    # Add user_id-updated_at-index
    success1 = add_index_if_not_exists(
        dynamodb, table_name, 'user_id-updated_at-index',
        key_schema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
        ],
        attribute_definitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'updated_at', 'AttributeType': 'S'}
        ]
    )
    
    return success1

def main():
    """Fix all missing indexes"""
    print("🔧 Fixing DynamoDB Indexes for Multi-Tenant Support")
    print("=" * 60)
    
    try:
        # Initialize DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        
        # Fix all tables
        fixes = [
            ("Canvases", fix_canvases_table),
            ("Chat Sessions", fix_chat_sessions_table),
            ("Chat Messages", fix_chat_messages_table),
            ("Files", fix_files_table),
            ("Workflows", fix_workflows_table),
        ]
        
        results = []
        
        for name, fix_func in fixes:
            try:
                success = fix_func(dynamodb)
                results.append((name, success))
            except Exception as e:
                print(f"❌ {name} failed: {e}")
                results.append((name, False))
        
        print("\n" + "=" * 60)
        print("📊 Index Fix Results:")
        
        passed = 0
        failed = 0
        
        for name, success in results:
            if success:
                print(f"  ✅ {name}")
                passed += 1
            else:
                print(f"  ❌ {name}")
                failed += 1
        
        print(f"\nTotal: {passed} successful, {failed} failed")
        
        if failed == 0:
            print("\n🎉 All indexes fixed successfully!")
            print("You can now restart the application.")
        else:
            print(f"\n⚠️ {failed} fix(es) failed. Check the errors above.")
        
        return failed == 0
        
    except Exception as e:
        print(f"❌ Failed to fix indexes: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
