# Jaaz Multi-Tenant Startup Guide

## 🚀 Quick Start

### 1. Prerequisites Check
Run the startup test to verify all dependencies:
```bash
python test_startup.py
```

### 2. Start the Application
```bash
./start-simple.sh
```

### 3. Access the Application
- Frontend: http://localhost:5174 (or your server IP)
- Backend: http://localhost:57988

## 🔐 Authentication Flow

### First Time Access
1. **Open the frontend** - You'll see a login dialog automatically
2. **Choose login method**:
   - **Username/Password Tab**: Use demo accounts
   - **Device Auth Tab**: Browser-based OAuth flow

### Demo Accounts
- **Admin**: `admin` / `admin123`
- **Demo**: `demo` / `demo123`

### User Registration
- Click the "Username/Password" tab in login dialog
- New users can register with username, email, and password
- Minimum requirements: 3+ char username, 6+ char password

## 🗄️ Database Schema

### Automatic Setup
The application automatically creates DynamoDB tables on first run:
- `jaaz-users` - User authentication data
- `jaaz-canvases` - User canvas projects
- `jaaz-chat-sessions` - Chat sessions per user
- `jaaz-chat-messages` - Messages with user isolation
- `jaaz-files` - User-specific file uploads
- `jaaz-comfy-workflows` - User workflow data

### Manual Migration (Optional)
If you want to run database migration manually:
```bash
cd server
python migrate_database.py
```

## 🔧 Configuration

### Environment Variables
```bash
# Optional - defaults work for development
export AWS_REGION=us-west-2
export DEVELOPMENT_MODE=true
```

### AWS Credentials
Configure AWS credentials for DynamoDB:
```bash
aws configure
# OR set environment variables:
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. "PyJWT not found"
```bash
cd server
pip install -r requirements.txt
```

#### 2. "AWS credentials not configured"
```bash
aws configure
# Enter your AWS credentials
```

#### 3. "Frontend dependencies missing"
```bash
cd react
npm install
```

#### 4. "Port already in use"
The start script automatically kills existing processes on ports 57988 and 5174.

#### 5. "Database connection failed"
- Check AWS credentials
- Verify internet connection
- Ensure DynamoDB access permissions

### Debug Mode
Check log files for detailed error information:
- Backend: `backend.log`
- Frontend: `frontend.log`

## 🔒 Security Features

### Multi-Tenant Isolation
- ✅ Users can only see their own canvases
- ✅ Chat sessions are user-specific
- ✅ File uploads are user-scoped
- ✅ WebSocket messages are filtered by user
- ✅ All API endpoints enforce user authentication

### Authentication
- ✅ JWT token-based authentication
- ✅ Password hashing with SHA256
- ✅ Token expiration (24 hours)
- ✅ Development mode auto-login for localhost

## 📊 User Management

### Admin Operations
Access user management at: `http://localhost:57988/api/auth/users`

### Password Changes
Users can change passwords through the API:
```bash
curl -X POST http://localhost:57988/api/auth/change-password \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"old_password": "old", "new_password": "new"}'
```

## 🔄 Development vs Production

### Development Mode (Default)
- Automatic user creation
- Localhost auto-authentication
- Demo accounts available
- Relaxed security for testing

### Production Mode
Set `DEVELOPMENT_MODE=false` and:
- Configure proper JWT secrets
- Set up real OAuth providers
- Enable HTTPS
- Configure proper AWS IAM roles

## 📝 API Endpoints

### Authentication
- `POST /api/auth/login` - Username/password login
- `POST /api/auth/register` - User registration
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/logout` - Logout

### Canvas Operations
- `GET /api/canvas/list` - List user's canvases
- `POST /api/canvas/create` - Create new canvas
- `GET /api/canvas/{id}` - Get canvas data
- `PUT /api/canvas/{id}` - Update canvas

All endpoints automatically enforce user isolation.

## 🎯 Next Steps

1. **Start the application**: `./start-simple.sh`
2. **Open browser**: Navigate to the frontend URL
3. **Login**: Use demo accounts or register new user
4. **Create canvas**: Start using the multi-tenant system!

## 📞 Support

If you encounter issues:
1. Run `python test_startup.py` to diagnose problems
2. Check log files for detailed error messages
3. Verify AWS credentials and permissions
4. Ensure all dependencies are installed
