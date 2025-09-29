# 🗄️ Database Version Management Guide

This guide explains how to switch between different database backend versions in Jaaz.

## 📋 Available Database Versions

### Version 1-4: SQLite Database (Legacy)
- **v1**: Initial schema (chat_sessions, chat_messages)
- **v2**: Add canvases table
- **v3**: Add comfy_workflows table  
- **v4**: Add files table
- **Use case**: Local development, single-user setups
- **Authentication**: None required

### Version 5: DynamoDB Legacy Schema
- **Backend**: AWS DynamoDB
- **Architecture**: Single-tenant (no user isolation)
- **Tables**: canvases, chat_sessions, chat_messages, comfy_workflows, files
- **Use case**: Cloud deployment without multi-tenancy
- **Authentication**: None required
- **Compatibility**: Works with old application code

### Version 6: DynamoDB Multi-tenant Schema ⭐ **Recommended**
- **Backend**: AWS DynamoDB
- **Architecture**: Multi-tenant with user isolation
- **Tables**: canvases, chat_sessions, chat_messages, comfy_workflows, files, users
- **Use case**: Production deployment with multiple users
- **Authentication**: JWT-based user authentication
- **Default users**: admin/admin123, demo/demo123

## 🚀 Quick Start

### 1. Check Available Versions
```bash
python server/switch_database_version.py list
```

### 2. Verify AWS Credentials (for DynamoDB versions)
```bash
python server/switch_database_version.py verify
```

### 3. Switch to Multi-tenant Version (Recommended)
```bash
python server/switch_database_version.py switch --version 6
```

### 4. Switch to Legacy DynamoDB Version
```bash
python server/switch_database_version.py switch --version 5
```

## 🔧 AWS Configuration

For DynamoDB versions (5 and 6), you need AWS credentials configured:

### Option 1: Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-west-2
```

### Option 2: AWS CLI
```bash
aws configure
```

### Option 3: AWS Credentials File
Create `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key
region = us-west-2
```

## 📊 Version Comparison

| Feature | SQLite (v1-4) | DynamoDB Legacy (v5) | DynamoDB Multi-tenant (v6) |
|---------|---------------|----------------------|----------------------------|
| Backend | SQLite | AWS DynamoDB | AWS DynamoDB |
| Scalability | Limited | High | High |
| Multi-tenancy | No | No | Yes |
| User Authentication | No | No | Yes |
| User Isolation | No | No | Yes |
| Cloud Ready | No | Yes | Yes |
| Cost | Free | Pay-per-use | Pay-per-use |
| Setup Complexity | Simple | Medium | Medium |

## 🔄 Migration Scenarios

### New Installation
```bash
# Recommended: Start with multi-tenant version
python server/switch_database_version.py switch --version 6
```

### Existing SQLite Users
```bash
# Option 1: Upgrade to multi-tenant (recommended)
python server/switch_database_version.py switch --version 6

# Option 2: Migrate to legacy DynamoDB (no authentication)
python server/switch_database_version.py switch --version 5
```

### Testing Different Versions
```bash
# Switch to version 6
python server/switch_database_version.py switch --version 6

# Test your application...

# Switch to version 5 for comparison
python server/switch_database_version.py switch --version 5
```

## 🗑️ Cleanup

⚠️ **Warning**: Cleanup operations will delete ALL data in the specified version!

```bash
# Clean up version 5 (legacy DynamoDB)
python server/switch_database_version.py cleanup --version 5

# Clean up version 6 (multi-tenant DynamoDB)
python server/switch_database_version.py cleanup --version 6
```

## 🔐 Authentication (Version 6 Only)

Version 6 includes user authentication with default users:

### Default Users
- **Admin**: username=`admin`, password=`admin123`
- **Demo**: username=`demo`, password=`demo123`

### API Authentication
All API endpoints require JWT tokens. Get a token by:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demo123"}'
```

Use the returned token in subsequent requests:
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api/canvases
```

## 🏗️ Application Configuration

### Version 5 (Legacy DynamoDB)
- No code changes required
- Works with existing application code
- No authentication middleware needed

### Version 6 (Multi-tenant DynamoDB)
- Authentication middleware automatically enabled
- User context automatically managed
- All database operations are user-isolated

## 🐛 Troubleshooting

### AWS Credentials Issues
```bash
# Verify credentials
python server/switch_database_version.py verify

# Check AWS CLI configuration
aws sts get-caller-identity
```

### DynamoDB Table Issues
```bash
# List existing tables
aws dynamodb list-tables --region us-west-2

# Check table status
aws dynamodb describe-table --table-name jaaz-canvases --region us-west-2
```

### Authentication Issues (Version 6)
- Check that default users were created
- Verify JWT token is valid
- Ensure Authorization header is included in requests

## 📝 Best Practices

1. **Start with Version 6**: For new projects, use the multi-tenant version
2. **Test Before Production**: Always test version switches in a development environment
3. **Backup Data**: Export important data before switching versions
4. **Monitor Costs**: DynamoDB charges based on usage
5. **Use IAM Roles**: In production, use IAM roles instead of access keys

## 🔗 Related Documentation

- [Multi-tenant Implementation Guide](MULTI_TENANT_IMPLEMENTATION.md)
- [Database Migration Guide](DATABASE_MIGRATION_GUIDE.md)
- [AWS DynamoDB Documentation](https://docs.aws.amazon.com/dynamodb/)
- [JWT Authentication Guide](https://jwt.io/introduction/)

## 💡 Tips

- Use `--force` flag to skip confirmation prompts in scripts
- Version 6 automatically creates user authentication tables
- DynamoDB tables are created in `us-west-2` region by default
- SQLite database files remain unchanged when switching to DynamoDB versions
