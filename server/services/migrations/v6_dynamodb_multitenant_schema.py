from . import Migration
import sqlite3
import boto3
from botocore.exceptions import ClientError


class V6DynamoDBMultitenantSchema(Migration):
    version = 6
    description = "Create DynamoDB tables with user_id (multi-tenant schema)"

    def __init__(self, region_name='us-west-2'):
        self.region_name = region_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.client = boto3.client('dynamodb', region_name=region_name)
        
        # Table names
        self.tables = {
            'canvases': 'jaaz-canvases',
            'chat_sessions': 'jaaz-chat-sessions',
            'chat_messages': 'jaaz-chat-messages',
            'comfy_workflows': 'jaaz-comfy-workflows',
            'files': 'jaaz-files',
            'users': 'jaaz-users',
            'db_version': 'jaaz-db-version'
        }

    def up(self, conn: sqlite3.Connection) -> None:
        """Create DynamoDB tables with multi-tenant schema (with user_id)"""
        print("🚀 Creating DynamoDB tables with multi-tenant schema...")
        
        try:
            # Create canvases table
            self._create_table_if_not_exists(
                table_name=self.tables['canvases'],
                key_schema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                    {'AttributeName': 'updated_at', 'AttributeType': 'S'}
                ],
                global_secondary_indexes=[
                    {
                        'IndexName': 'user_id-updated_at-index',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'updated_at-index',
                        'KeySchema': [
                            {'AttributeName': 'updated_at', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ]
            )
            
            # Create chat_sessions table
            self._create_table_if_not_exists(
                table_name=self.tables['chat_sessions'],
                key_schema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                    {'AttributeName': 'canvas_id', 'AttributeType': 'S'},
                    {'AttributeName': 'updated_at', 'AttributeType': 'S'}
                ],
                global_secondary_indexes=[
                    {
                        'IndexName': 'user_id-updated_at-index',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'canvas_id-updated_at-index',
                        'KeySchema': [
                            {'AttributeName': 'canvas_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ]
            )
            
            # Create chat_messages table
            self._create_table_if_not_exists(
                table_name=self.tables['chat_messages'],
                key_schema=[
                    {'AttributeName': 'session_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'id', 'KeyType': 'RANGE'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'session_id', 'AttributeType': 'S'},
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'}
                ],
                global_secondary_indexes=[
                    {
                        'IndexName': 'user_id-session_id-index',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'session_id', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ]
            )
            
            # Create comfy_workflows table
            self._create_table_if_not_exists(
                table_name=self.tables['comfy_workflows'],
                key_schema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                    {'AttributeName': 'updated_at', 'AttributeType': 'S'}
                ],
                global_secondary_indexes=[
                    {
                        'IndexName': 'user_id-updated_at-index',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'updated_at-index',
                        'KeySchema': [
                            {'AttributeName': 'updated_at', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ]
            )
            
            # Create files table
            self._create_table_if_not_exists(
                table_name=self.tables['files'],
                key_schema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                    {'AttributeName': 'created_at', 'AttributeType': 'S'}
                ],
                global_secondary_indexes=[
                    {
                        'IndexName': 'user_id-created_at-index',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'created_at-index',
                        'KeySchema': [
                            {'AttributeName': 'created_at', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ]
            )

            # Create users table
            self._create_table_if_not_exists(
                table_name=self.tables['users'],
                key_schema=[
                    {'AttributeName': 'username', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'username', 'AttributeType': 'S'},
                    {'AttributeName': 'email', 'AttributeType': 'S'},
                    {'AttributeName': 'created_at', 'AttributeType': 'S'}
                ],
                global_secondary_indexes=[
                    {
                        'IndexName': 'email-index',
                        'KeySchema': [
                            {'AttributeName': 'email', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'created_at-index',
                        'KeySchema': [
                            {'AttributeName': 'created_at', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ]
            )

            # Create db_version table
            self._create_table_if_not_exists(
                table_name=self.tables['db_version'],
                key_schema=[
                    {'AttributeName': 'version', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'version', 'AttributeType': 'N'}
                ]
            )
            
            print("✅ DynamoDB multi-tenant schema tables created successfully")
            
            # Initialize default users
            self._create_default_users()
            
        except Exception as e:
            print(f"❌ Error creating DynamoDB multi-tenant schema: {e}")
            raise

    def down(self, conn: sqlite3.Connection) -> None:
        """Delete DynamoDB tables"""
        print("🗑️ Deleting DynamoDB multi-tenant schema tables...")
        
        try:
            for table_name in self.tables.values():
                try:
                    self.client.delete_table(TableName=table_name)
                    print(f"Deleted table {table_name}")
                except ClientError as e:
                    if e.response['Error']['Code'] != 'ResourceNotFoundException':
                        print(f"Error deleting table {table_name}: {e}")
            
            print("✅ DynamoDB multi-tenant schema tables deleted successfully")
            
        except Exception as e:
            print(f"❌ Error deleting DynamoDB multi-tenant schema: {e}")
            raise

    def _create_table_if_not_exists(self, table_name: str, key_schema: list,
                                   attribute_definitions: list,
                                   global_secondary_indexes: list = None):
        """Create a table if it doesn't exist"""
        try:
            # Check if table exists
            self.client.describe_table(TableName=table_name)
            print(f"Table {table_name} already exists")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Table doesn't exist, create it
                print(f"Creating table {table_name}")

                table_params = {
                    'TableName': table_name,
                    'KeySchema': key_schema,
                    'AttributeDefinitions': attribute_definitions,
                    'BillingMode': 'PROVISIONED',
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }

                if global_secondary_indexes:
                    table_params['GlobalSecondaryIndexes'] = global_secondary_indexes

                self.client.create_table(**table_params)

                # Wait for table to be created
                waiter = self.client.get_waiter('table_exists')
                waiter.wait(TableName=table_name)
                print(f"Table {table_name} created successfully")
            else:
                raise

    def _create_default_users(self):
        """Create default users for the system"""
        try:
            import hashlib
            import uuid
            from datetime import datetime

            users_table = self.dynamodb.Table(self.tables['users'])
            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

            # Create admin user
            admin_password_hash = hashlib.sha256("admin123".encode()).hexdigest()
            admin_user = {
                'username': 'admin',
                'user_id': f"user_{uuid.uuid4().hex[:8]}",
                'email': 'admin@jaaz.ai',
                'password_hash': admin_password_hash,
                'created_at': timestamp,
                'updated_at': timestamp,
                'is_active': True,
                'last_login': None
            }

            # Create demo user
            demo_password_hash = hashlib.sha256("demo123".encode()).hexdigest()
            demo_user = {
                'username': 'demo',
                'user_id': f"user_{uuid.uuid4().hex[:8]}",
                'email': 'demo@jaaz.ai',
                'password_hash': demo_password_hash,
                'created_at': timestamp,
                'updated_at': timestamp,
                'is_active': True,
                'last_login': None
            }

            # Insert users (ignore if they already exist)
            try:
                users_table.put_item(
                    Item=admin_user,
                    ConditionExpression='attribute_not_exists(username)'
                )
                print("✅ Created admin user")
            except ClientError as e:
                if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    raise
                print("ℹ️ Admin user already exists")

            try:
                users_table.put_item(
                    Item=demo_user,
                    ConditionExpression='attribute_not_exists(username)'
                )
                print("✅ Created demo user")
            except ClientError as e:
                if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    raise
                print("ℹ️ Demo user already exists")

        except Exception as e:
            print(f"❌ Error creating default users: {e}")
            raise
