import boto3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError
import uuid

class DynamoDBService:
    def __init__(self, region_name='us-west-2'):
        """Initialize DynamoDB service"""
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
        
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """Create tables if they don't exist"""
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
            
        except Exception as e:
            print(f"Error creating DynamoDB tables: {e}")
            raise
    
    def _create_table_if_not_exists(self, table_name: str, key_schema: List[Dict], 
                                   attribute_definitions: List[Dict], 
                                   global_secondary_indexes: List[Dict] = None):
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
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    # Canvas operations
    def create_canvas(self, id: str, name: str, user_id: str):
        """Create a new canvas"""
        table = self.dynamodb.Table(self.tables['canvases'])
        timestamp = self._get_current_timestamp()

        item = {
            'id': id,
            'name': name,
            'user_id': user_id,
            'description': '',
            'thumbnail': '',
            'created_at': timestamp,
            'updated_at': timestamp
        }

        table.put_item(Item=item)

    def list_canvases(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all canvases for a specific user"""
        table = self.dynamodb.Table(self.tables['canvases'])

        response = table.query(
            IndexName='user_id-updated_at-index',
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': user_id},
            ScanIndexForward=False  # Sort by updated_at DESC
        )

        return response.get('Items', [])

    def get_canvas(self, id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Get canvas by ID with optional user verification"""
        table = self.dynamodb.Table(self.tables['canvases'])

        response = table.get_item(Key={'id': id})
        canvas = response.get('Item')

        # If user_id is provided, verify ownership
        if canvas and user_id and canvas.get('user_id') != user_id:
            return None

        return canvas

    def save_canvas_data(self, id: str, data: str, user_id: str, thumbnail: str = None):
        """Save canvas data with user verification"""
        table = self.dynamodb.Table(self.tables['canvases'])
        timestamp = self._get_current_timestamp()

        # First verify user owns this canvas
        canvas = self.get_canvas(id, user_id)
        if not canvas:
            raise ValueError(f"Canvas {id} not found or access denied for user {user_id}")

        update_expression = "SET #data = :data, updated_at = :updated_at"
        expression_attribute_names = {'#data': 'data'}
        expression_attribute_values = {
            ':data': data,
            ':updated_at': timestamp
        }

        if thumbnail:
            update_expression += ", thumbnail = :thumbnail"
            expression_attribute_values[':thumbnail'] = thumbnail

        table.update_item(
            Key={'id': id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )

    def rename_canvas(self, id: str, name: str, user_id: str):
        """Rename canvas with user verification"""
        table = self.dynamodb.Table(self.tables['canvases'])
        timestamp = self._get_current_timestamp()

        # First verify user owns this canvas
        canvas = self.get_canvas(id, user_id)
        if not canvas:
            raise ValueError(f"Canvas {id} not found or access denied for user {user_id}")

        table.update_item(
            Key={'id': id},
            UpdateExpression="SET #name = :name, updated_at = :updated_at",
            ExpressionAttributeNames={'#name': 'name'},
            ExpressionAttributeValues={
                ':name': name,
                ':updated_at': timestamp
            }
        )

    def delete_canvas(self, id: str, user_id: str):
        """Delete canvas with user verification"""
        table = self.dynamodb.Table(self.tables['canvases'])

        # First verify user owns this canvas
        canvas = self.get_canvas(id, user_id)
        if not canvas:
            raise ValueError(f"Canvas {id} not found or access denied for user {user_id}")

        table.delete_item(Key={'id': id})

    # Chat session operations
    def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, user_id: str, title: Optional[str] = None):
        """Save a new chat session"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])
        timestamp = self._get_current_timestamp()

        # Verify user owns the canvas
        canvas = self.get_canvas(canvas_id, user_id)
        if not canvas:
            raise ValueError(f"Canvas {canvas_id} not found or access denied for user {user_id}")

        item = {
            'id': id,
            'model': model,
            'provider': provider,
            'canvas_id': canvas_id,
            'user_id': user_id,
            'title': title or '',
            'created_at': timestamp,
            'updated_at': timestamp
        }

        table.put_item(Item=item)

    def list_chat_sessions(self, canvas_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get chat sessions for a canvas with user verification"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])

        # Verify user owns the canvas
        canvas = self.get_canvas(canvas_id, user_id)
        if not canvas:
            raise ValueError(f"Canvas {canvas_id} not found or access denied for user {user_id}")

        response = table.query(
            IndexName='canvas_id-updated_at-index',
            KeyConditionExpression='canvas_id = :canvas_id',
            ExpressionAttributeValues={':canvas_id': canvas_id},
            ScanIndexForward=False  # Sort by updated_at DESC
        )

        return response.get('Items', [])

    def list_user_chat_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all chat sessions for a user"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])

        response = table.query(
            IndexName='user_id-updated_at-index',
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': user_id},
            ScanIndexForward=False  # Sort by updated_at DESC
        )

        return response.get('Items', [])

    def get_chat_session(self, id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Get chat session by ID with optional user verification"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])

        response = table.get_item(Key={'id': id})
        session = response.get('Item')

        # If user_id is provided, verify ownership
        if session and user_id and session.get('user_id') != user_id:
            return None

        return session

    def update_chat_session_title(self, id: str, title: str, user_id: str):
        """Update chat session title with user verification"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])
        timestamp = self._get_current_timestamp()

        # First verify user owns this session
        session = self.get_chat_session(id, user_id)
        if not session:
            raise ValueError(f"Chat session {id} not found or access denied for user {user_id}")

        table.update_item(
            Key={'id': id},
            UpdateExpression="SET title = :title, updated_at = :updated_at",
            ExpressionAttributeValues={
                ':title': title,
                ':updated_at': timestamp
            }
        )

    def delete_chat_session(self, id: str, user_id: str):
        """Delete chat session with user verification"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])

        # First verify user owns this session
        session = self.get_chat_session(id, user_id)
        if not session:
            raise ValueError(f"Chat session {id} not found or access denied for user {user_id}")

        table.delete_item(Key={'id': id})

    # Chat message operations
    def create_message(self, session_id: str, role: str, message: str, user_id: str):
        """Save a chat message with user verification"""
        table = self.dynamodb.Table(self.tables['chat_messages'])
        timestamp = self._get_current_timestamp()

        # Verify user owns the session
        session = self.get_chat_session(session_id, user_id)
        if not session:
            raise ValueError(f"Chat session {session_id} not found or access denied for user {user_id}")

        # Use timestamp with microseconds as sort key to maintain order
        # Format: YYYYMMDD_HHMMSS_microseconds
        from datetime import datetime
        now = datetime.utcnow()
        message_id = now.strftime('%Y%m%d_%H%M%S_%f')

        item = {
            'session_id': session_id,
            'id': message_id,
            'user_id': user_id,
            'role': role,
            'message': message,
            'created_at': timestamp,
            'updated_at': timestamp
        }

        table.put_item(Item=item)

    def list_messages(self, session_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get messages for a chat session with user verification"""
        table = self.dynamodb.Table(self.tables['chat_messages'])

        # Verify user owns the session
        session = self.get_chat_session(session_id, user_id)
        if not session:
            raise ValueError(f"Chat session {session_id} not found or access denied for user {user_id}")

        response = table.query(
            KeyConditionExpression='session_id = :session_id',
            ExpressionAttributeValues={':session_id': session_id},
            ScanIndexForward=True  # Sort by id ASC (chronological order)
        )

        items = response.get('Items', [])
        # Additional sorting by created_at as backup in case id sorting isn't perfect
        items.sort(key=lambda x: x.get('created_at', ''))

        return items

    # ComfyUI workflow operations
    def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, user_id: str, outputs: str = None):
        """Create a new comfy workflow"""
        table = self.dynamodb.Table(self.tables['comfy_workflows'])
        timestamp = self._get_current_timestamp()
        workflow_id = str(uuid.uuid4())

        item = {
            'id': workflow_id,
            'name': name,
            'user_id': user_id,
            'api_json': api_json,
            'description': description,
            'inputs': inputs,
            'outputs': outputs or '',
            'created_at': timestamp,
            'updated_at': timestamp
        }

        table.put_item(Item=item)

    def list_comfy_workflows(self, user_id: str) -> List[Dict[str, Any]]:
        """List comfy workflows for a specific user"""
        table = self.dynamodb.Table(self.tables['comfy_workflows'])

        response = table.query(
            IndexName='user_id-updated_at-index',
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': user_id},
            ScanIndexForward=False  # Sort by updated_at DESC
        )

        return response.get('Items', [])

    def get_comfy_workflow(self, id: int, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Get comfy workflow by ID with optional user verification"""
        table = self.dynamodb.Table(self.tables['comfy_workflows'])

        response = table.get_item(Key={'id': str(id)})
        workflow = response.get('Item')

        # If user_id is provided, verify ownership
        if workflow and user_id and workflow.get('user_id') != user_id:
            return None

        return workflow

    def delete_comfy_workflow(self, id: int, user_id: str):
        """Delete a comfy workflow with user verification"""
        table = self.dynamodb.Table(self.tables['comfy_workflows'])

        # First verify user owns this workflow
        workflow = self.get_comfy_workflow(id, user_id)
        if not workflow:
            raise ValueError(f"Workflow {id} not found or access denied for user {user_id}")

        table.delete_item(Key={'id': str(id)})

    # File operations
    def create_file(self, file_id: str, file_path: str, user_id: str, width: int = None, height: int = None):
        """Create a new file record"""
        table = self.dynamodb.Table(self.tables['files'])
        timestamp = self._get_current_timestamp()

        item = {
            'id': file_id,
            'file_path': file_path,
            'user_id': user_id,
            'created_at': timestamp,
            'updated_at': timestamp
        }

        if width is not None:
            item['width'] = width
        if height is not None:
            item['height'] = height

        table.put_item(Item=item)

    def get_file(self, file_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Get file record by ID with optional user verification"""
        table = self.dynamodb.Table(self.tables['files'])

        response = table.get_item(Key={'id': file_id})
        file_record = response.get('Item')

        # If user_id is provided, verify ownership
        if file_record and user_id and file_record.get('user_id') != user_id:
            return None

        return file_record

    def list_files(self, user_id: str) -> List[Dict[str, Any]]:
        """List files for a specific user"""
        table = self.dynamodb.Table(self.tables['files'])

        response = table.query(
            IndexName='user_id-created_at-index',
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': user_id},
            ScanIndexForward=False  # Sort by created_at DESC
        )

        return response.get('Items', [])

    def delete_file(self, file_id: str, user_id: str):
        """Delete a file record with user verification"""
        table = self.dynamodb.Table(self.tables['files'])

        # First verify user owns this file
        file_record = self.get_file(file_id, user_id)
        if not file_record:
            raise ValueError(f"File {file_id} not found or access denied for user {user_id}")

        table.delete_item(Key={'id': file_id})

    # User operations
    def create_user(self, username: str, email: str, password_hash: str, user_id: str):
        """Create a new user"""
        table = self.dynamodb.Table(self.tables['users'])
        timestamp = self._get_current_timestamp()

        item = {
            'username': username.lower(),
            'user_id': user_id,
            'email': email.lower(),
            'password_hash': password_hash,
            'created_at': timestamp,
            'updated_at': timestamp,
            'is_active': True,
            'last_login': None
        }

        table.put_item(Item=item)

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        table = self.dynamodb.Table(self.tables['users'])

        response = table.get_item(Key={'username': username.lower()})
        return response.get('Item')

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        table = self.dynamodb.Table(self.tables['users'])

        response = table.query(
            IndexName='email-index',
            KeyConditionExpression='email = :email',
            ExpressionAttributeValues={':email': email.lower()}
        )

        items = response.get('Items', [])
        return items[0] if items else None

    def update_user_last_login(self, username: str):
        """Update user's last login timestamp"""
        table = self.dynamodb.Table(self.tables['users'])
        timestamp = self._get_current_timestamp()

        table.update_item(
            Key={'username': username.lower()},
            UpdateExpression="SET last_login = :last_login, updated_at = :updated_at",
            ExpressionAttributeValues={
                ':last_login': timestamp,
                ':updated_at': timestamp
            }
        )

    def update_user_password(self, username: str, new_password_hash: str):
        """Update user's password"""
        table = self.dynamodb.Table(self.tables['users'])
        timestamp = self._get_current_timestamp()

        table.update_item(
            Key={'username': username.lower()},
            UpdateExpression="SET password_hash = :password_hash, updated_at = :updated_at",
            ExpressionAttributeValues={
                ':password_hash': new_password_hash,
                ':updated_at': timestamp
            }
        )

    def deactivate_user(self, username: str):
        """Deactivate a user account"""
        table = self.dynamodb.Table(self.tables['users'])
        timestamp = self._get_current_timestamp()

        table.update_item(
            Key={'username': username.lower()},
            UpdateExpression="SET is_active = :is_active, updated_at = :updated_at",
            ExpressionAttributeValues={
                ':is_active': False,
                ':updated_at': timestamp
            }
        )

    def list_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all users (for admin purposes)"""
        table = self.dynamodb.Table(self.tables['users'])

        response = table.scan(Limit=limit)
        items = response.get('Items', [])

        # Sort by created_at DESC
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return items

    # Database version operations
    def get_db_version(self) -> int:
        """Get current database version"""
        table = self.dynamodb.Table(self.tables['db_version'])

        response = table.scan()
        items = response.get('Items', [])

        if not items:
            return 0

        # Return the highest version number
        return max(int(item['version']) for item in items)

    def set_db_version(self, version: int):
        """Set database version"""
        table = self.dynamodb.Table(self.tables['db_version'])

        table.put_item(Item={'version': version})
