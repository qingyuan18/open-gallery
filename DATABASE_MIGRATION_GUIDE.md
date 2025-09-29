# Database Migration Guide: SQLite to DynamoDB

This guide explains how to migrate your Jaaz application from SQLite to AWS DynamoDB while keeping SQLite as a backup option.

## Overview

The application now supports both SQLite and DynamoDB as database backends:

- **SQLite**: Local file-based database (default)
- **DynamoDB**: AWS cloud-based NoSQL database with automatic backup to SQLite

## Features

- **Dual Database Support**: Use DynamoDB as primary with SQLite as backup
- **Automatic Fallback**: If DynamoDB fails, operations fall back to SQLite
- **Data Synchronization**: Write operations are synchronized to both databases when using DynamoDB
- **Easy Migration**: Tools provided to migrate existing SQLite data to DynamoDB

## Prerequisites

1. **AWS Credentials**: Ensure your server has AWS credentials configured
   - IAM role with DynamoDB permissions (recommended for EC2)
   - Or AWS credentials file (`~/.aws/credentials`)
   - Or environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)

2. **DynamoDB Permissions**: Your AWS credentials need the following permissions:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "dynamodb:CreateTable",
           "dynamodb:DescribeTable",
           "dynamodb:PutItem",
           "dynamodb:GetItem",
           "dynamodb:UpdateItem",
           "dynamodb:DeleteItem",
           "dynamodb:Query",
           "dynamodb:Scan"
         ],
         "Resource": "arn:aws:dynamodb:*:*:table/jaaz-*"
       }
     ]
   }
   ```

## Configuration

### 1. Update Configuration File

Create or update `user_data/config.toml`:

```toml
[database]
type = "dynamodb"  # Use "sqlite" for SQLite only, "dynamodb" for DynamoDB with SQLite backup

[database.dynamodb]
region = "us-west-2"  # Your AWS region

[database.sqlite]
# Optional: custom SQLite path for backup
# path = "/custom/path/to/backup.db"
```

### 2. Example Configuration

See `server/config_example_dynamodb.toml` for a complete configuration example.

## Migration Process

### Step 1: Backup Your Data

Before migrating, backup your existing SQLite database:

```bash
cp user_data/localmanus.db user_data/localmanus_backup.db
```

### Step 2: Run Migration Tool

Use the provided migration tool to transfer data from SQLite to DynamoDB:

```bash
cd server
python tools/migrate_to_dynamodb.py
```

#### Migration Options

- **Dry Run**: See what would be migrated without actually migrating
  ```bash
  python tools/migrate_to_dynamodb.py --dry-run
  ```

- **Custom SQLite Path**: Specify a different SQLite database file
  ```bash
  python tools/migrate_to_dynamodb.py --sqlite-path /path/to/your/database.db
  ```

- **Custom Region**: Specify a different AWS region
  ```bash
  python tools/migrate_to_dynamodb.py --dynamodb-region us-east-1
  ```

### Step 3: Update Configuration

After successful migration, update your `user_data/config.toml` to use DynamoDB:

```toml
[database]
type = "dynamodb"
```

### Step 4: Restart Application

Restart your Jaaz application. It will now use DynamoDB as the primary database with SQLite as backup.

## DynamoDB Tables

The migration creates the following DynamoDB tables:

- `jaaz-canvases`: Canvas data and metadata
- `jaaz-chat-sessions`: Chat session information
- `jaaz-chat-messages`: Individual chat messages
- `jaaz-comfy-workflows`: ComfyUI workflow definitions
- `jaaz-files`: File metadata
- `jaaz-db-version`: Database schema version

## Monitoring and Troubleshooting

### Check Application Logs

The application logs will show which database is being used:

```
Initializing DynamoDB as primary database
Initializing SQLite as backup database
```

### Fallback Behavior

If DynamoDB operations fail, the application will:

1. Log the error
2. Attempt the operation on SQLite backup
3. Continue operation with SQLite if DynamoDB is unavailable

### Common Issues

1. **AWS Credentials Not Found**
   - Ensure AWS credentials are properly configured
   - Check IAM permissions for DynamoDB access

2. **Region Mismatch**
   - Verify the region in your configuration matches your AWS setup
   - Ensure DynamoDB is available in your chosen region

3. **Table Creation Fails**
   - Check DynamoDB permissions
   - Verify you have sufficient AWS service limits

## Rolling Back

To roll back to SQLite-only mode:

1. Update `user_data/config.toml`:
   ```toml
   [database]
   type = "sqlite"
   ```

2. Restart the application

Your SQLite backup will continue to work as before.

## Cost Considerations

DynamoDB pricing is based on:
- **Provisioned Capacity**: Read/write capacity units (default: 5 RCU/WCU per table)
- **Storage**: Data stored in tables
- **Requests**: API requests to DynamoDB

For typical Jaaz usage, costs should be minimal, but monitor your AWS billing dashboard.

## Support

If you encounter issues during migration:

1. Check the application logs for error messages
2. Verify AWS credentials and permissions
3. Ensure network connectivity to AWS DynamoDB
4. Use the dry-run option to test migration before executing

The application is designed to gracefully handle database failures and maintain functionality even if DynamoDB becomes unavailable.
