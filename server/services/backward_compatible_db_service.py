"""
Backward compatible database service that works with both old and new data
"""
from typing import Dict, Any, Optional, List
from .dynamodb_service import DynamoDBService
import boto3
from botocore.exceptions import ClientError


class BackwardCompatibleDatabaseService(DynamoDBService):
    """Database service that maintains backward compatibility with pre-multi-tenant data"""
    
    def __init__(self, region_name='us-west-2'):
        super().__init__(region_name)
        self._migration_mode = self._detect_migration_mode()
    
    def _detect_migration_mode(self) -> str:
        """Detect if we're in legacy mode, migration mode, or full multi-tenant mode"""
        try:
            # Check if user_id-updated_at-index exists on canvases table
            table = self.dynamodb.Table(self.tables['canvases'])
            table.load()
            
            indexes = table.global_secondary_indexes or []
            has_user_index = any(idx['IndexName'] == 'user_id-updated_at-index' for idx in indexes)
            
            if has_user_index:
                # Check if we have any records without user_id (legacy data)
                response = table.scan(Limit=10)
                items = response.get('Items', [])
                
                has_legacy_data = any('user_id' not in item for item in items)
                
                if has_legacy_data:
                    print("🔄 Migration mode: Found legacy data without user_id")
                    return "migration"
                else:
                    print("✅ Multi-tenant mode: All data has user_id")
                    return "multi_tenant"
            else:
                print("📊 Legacy mode: No multi-tenant indexes found")
                return "legacy"
                
        except Exception as e:
            print(f"⚠️ Could not detect migration mode: {e}")
            return "legacy"
    
    def list_canvases(self, user_id: str = None) -> List[Dict[str, Any]]:
        """Get canvases with backward compatibility"""
        table = self.dynamodb.Table(self.tables['canvases'])
        
        try:
            if self._migration_mode == "legacy":
                # Legacy mode: scan all canvases (no user filtering)
                print("📊 Legacy mode: Returning all canvases")
                response = table.scan()
                items = response.get('Items', [])
                
                # Sort by updated_at DESC
                items.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
                return items
                
            elif self._migration_mode == "migration":
                # Migration mode: try user query first, fallback to scan
                if user_id:
                    try:
                        # Try to query by user_id
                        response = table.query(
                            IndexName='user_id-updated_at-index',
                            KeyConditionExpression='user_id = :user_id',
                            ExpressionAttributeValues={':user_id': user_id},
                            ScanIndexForward=False
                        )
                        user_items = response.get('Items', [])
                        
                        # Also get legacy items (without user_id) and assign to current user
                        legacy_response = table.scan(
                            FilterExpression='attribute_not_exists(user_id)'
                        )
                        legacy_items = legacy_response.get('Items', [])
                        
                        # Migrate legacy items to current user
                        for item in legacy_items:
                            try:
                                self._migrate_canvas_to_user(item['id'], user_id)
                                item['user_id'] = user_id  # Add to response
                                user_items.append(item)
                            except Exception as e:
                                print(f"⚠️ Failed to migrate canvas {item.get('id')}: {e}")
                        
                        # Sort by updated_at DESC
                        user_items.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
                        return user_items
                        
                    except ClientError as e:
                        if 'ValidationException' in str(e):
                            # Index doesn't exist, fallback to scan
                            print("📊 Index not found, falling back to scan")
                            return self._scan_all_canvases()
                        raise
                else:
                    return self._scan_all_canvases()
                    
            else:  # multi_tenant mode
                # Full multi-tenant mode
                if not user_id:
                    raise ValueError("user_id is required in multi-tenant mode")
                
                response = table.query(
                    IndexName='user_id-updated_at-index',
                    KeyConditionExpression='user_id = :user_id',
                    ExpressionAttributeValues={':user_id': user_id},
                    ScanIndexForward=False
                )
                return response.get('Items', [])
                
        except Exception as e:
            print(f"⚠️ Error in list_canvases: {e}")
            # Fallback to scan
            return self._scan_all_canvases()
    
    def _scan_all_canvases(self) -> List[Dict[str, Any]]:
        """Fallback method to scan all canvases"""
        table = self.dynamodb.Table(self.tables['canvases'])
        response = table.scan()
        items = response.get('Items', [])
        items.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        return items
    
    def _migrate_canvas_to_user(self, canvas_id: str, user_id: str):
        """Migrate a legacy canvas to a specific user"""
        table = self.dynamodb.Table(self.tables['canvases'])
        
        try:
            # Update the canvas with user_id
            table.update_item(
                Key={'id': canvas_id},
                UpdateExpression="SET user_id = :user_id",
                ExpressionAttributeValues={':user_id': user_id}
            )
            print(f"✅ Migrated canvas {canvas_id} to user {user_id}")
        except Exception as e:
            print(f"❌ Failed to migrate canvas {canvas_id}: {e}")
            raise
    
    def get_canvas(self, id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Get canvas with backward compatibility"""
        table = self.dynamodb.Table(self.tables['canvases'])
        
        try:
            response = table.get_item(Key={'id': id})
            item = response.get('Item')
            
            if not item:
                return None
            
            # In legacy mode, return any canvas
            if self._migration_mode == "legacy":
                return item
            
            # In migration mode, check user_id or migrate
            if self._migration_mode == "migration":
                if 'user_id' not in item:
                    # Legacy item, migrate it to current user
                    if user_id:
                        self._migrate_canvas_to_user(id, user_id)
                        item['user_id'] = user_id
                    return item
                elif user_id and item.get('user_id') != user_id:
                    # User doesn't own this canvas
                    return None
                else:
                    return item
            
            # In multi-tenant mode, strict user verification
            if user_id and item.get('user_id') != user_id:
                return None
            
            return item
            
        except Exception as e:
            print(f"⚠️ Error getting canvas {id}: {e}")
            return None
    
    def create_canvas(self, id: str, name: str, user_id: str = None):
        """Create canvas with user_id if provided"""
        table = self.dynamodb.Table(self.tables['canvases'])
        timestamp = self._get_current_timestamp()

        item = {
            'id': id,
            'name': name,
            'created_at': timestamp,
            'updated_at': timestamp,
            'data': '',
            'thumbnail': ''
        }
        
        # Add user_id if provided (multi-tenant mode)
        if user_id:
            item['user_id'] = user_id

        table.put_item(Item=item)
    
    def save_canvas_data(self, id: str, data: str, user_id: str = None, thumbnail: str = None):
        """Save canvas data with optional user verification"""
        # First verify user owns this canvas (if in multi-tenant mode)
        if user_id and self._migration_mode != "legacy":
            canvas = self.get_canvas(id, user_id)
            if not canvas:
                raise ValueError(f"Canvas {id} not found or access denied for user {user_id}")
        
        table = self.dynamodb.Table(self.tables['canvases'])
        timestamp = self._get_current_timestamp()

        update_expression = "SET #data = :data, updated_at = :updated_at"
        expression_attribute_names = {'#data': 'data'}
        expression_attribute_values = {
            ':data': data,
            ':updated_at': timestamp
        }

        if thumbnail is not None:
            update_expression += ", thumbnail = :thumbnail"
            expression_attribute_values[':thumbnail'] = thumbnail

        # Add user_id if not present (migration)
        if user_id and self._migration_mode == "migration":
            update_expression += ", user_id = :user_id"
            expression_attribute_values[':user_id'] = user_id

        table.update_item(
            Key={'id': id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get migration status information"""
        return {
            "mode": self._migration_mode,
            "description": {
                "legacy": "Pre-multi-tenant mode - no user isolation",
                "migration": "Migration mode - legacy data being migrated",
                "multi_tenant": "Full multi-tenant mode - complete user isolation"
            }.get(self._migration_mode, "Unknown"),
            "recommendations": self._get_migration_recommendations()
        }
    
    def _get_migration_recommendations(self) -> List[str]:
        """Get recommendations based on current mode"""
        if self._migration_mode == "legacy":
            return [
                "Run database migration to add multi-tenant support",
                "Create missing indexes with: python server/fix_database_indexes.py",
                "Consider backing up data before migration"
            ]
        elif self._migration_mode == "migration":
            return [
                "Legacy data will be automatically migrated when accessed",
                "Monitor logs for migration progress",
                "Consider running full migration script for better performance"
            ]
        else:
            return [
                "System is fully multi-tenant",
                "All data is properly isolated by user"
            ]


# Create a global instance
backward_compatible_db_service = BackwardCompatibleDatabaseService()
