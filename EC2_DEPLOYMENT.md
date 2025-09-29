# EC2 Deployment Guide

This guide explains how to deploy the Jaaz application on AWS EC2 with proper network configuration.

## Prerequisites

1. **EC2 Instance**: Running Ubuntu/Amazon Linux with sufficient resources
2. **Security Groups**: Properly configured to allow traffic
3. **Domain/IP Access**: Public IP or domain name for external access

## Security Group Configuration

### Required Inbound Rules

| Type | Protocol | Port Range | Source | Description |
|------|----------|------------|--------|-------------|
| HTTP | TCP | 80 | 0.0.0.0/0 | Web traffic (optional, for reverse proxy) |
| HTTPS | TCP | 443 | 0.0.0.0/0 | Secure web traffic (optional, for reverse proxy) |
| Custom TCP | TCP | 5174 | 0.0.0.0/0 | Frontend development server |
| Custom TCP | TCP | 57988 | 0.0.0.0/0 | Backend API server |
| SSH | TCP | 22 | Your IP | SSH access |

**⚠️ Security Note**: For production, consider restricting access to specific IP ranges instead of 0.0.0.0/0.

## Installation Steps

### 1. System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Node.js (18+)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Python 3.9+
sudo apt install python3 python3-pip python3-venv -y

# Install Git
sudo apt install git -y
```

### 2. Clone and Setup Project

```bash
# Clone the repository
git clone <your-repo-url> jaaz
cd jaaz

# Setup Python virtual environment
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup Node.js dependencies
cd ../react
npm install
```

### 3. Configure Application

#### Backend Configuration
```bash
cd server

# Create user data directory
mkdir -p user_data

# Configure Bedrock (if using AWS Bedrock)
cat > user_data/config.toml << EOF
[bedrock]
region = "us-west-2"  # Your EC2 region

[bedrock.models]
"anthropic.claude-3-5-sonnet-20241022-v2:0" = { type = "text" }
"anthropic.claude-3-5-haiku-20241022-v1:0" = { type = "text" }
EOF
```

#### Frontend Configuration
The application is already configured to work with 0.0.0.0 binding and allows all hosts.

### 4. AWS Credentials (for Bedrock)

```bash
# Option 1: AWS CLI
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-west-2

# Option 3: IAM Role (recommended for EC2)
# Attach an IAM role with Bedrock permissions to your EC2 instance
```

## Running the Application

### Development Mode

#### Terminal 1 - Backend
```bash
cd server
source venv/bin/activate
python main.py --port 57988
```

#### Terminal 2 - Frontend
```bash
cd react
npm run dev
```

### Production Mode with PM2

#### Install PM2
```bash
sudo npm install -g pm2
```

#### Create PM2 Configuration
```bash
cat > ecosystem.config.js << EOF
module.exports = {
  apps: [
    {
      name: 'jaaz-backend',
      script: 'server/main.py',
      args: '--port 57988',
      interpreter: 'server/venv/bin/python',
      cwd: '/home/ubuntu/jaaz',
      env: {
        NODE_ENV: 'production'
      }
    },
    {
      name: 'jaaz-frontend',
      script: 'npm',
      args: 'run dev',
      cwd: '/home/ubuntu/jaaz/react',
      env: {
        NODE_ENV: 'production'
      }
    }
  ]
};
EOF
```

#### Start Services
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

## Access URLs

After deployment, access your application at:

- **Frontend**: `http://your-ec2-public-ip:5174`
- **Backend API**: `http://your-ec2-public-ip:57988`
- **Example**: `http://ec2-52-24-176-86.us-west-2.compute.amazonaws.com:5174`

## Reverse Proxy Setup (Optional)

For production, consider using Nginx as a reverse proxy:

### Install Nginx
```bash
sudo apt install nginx -y
```

### Configure Nginx
```bash
sudo cat > /etc/nginx/sites-available/jaaz << EOF
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or IP

    # Frontend
    location / {
        proxy_pass http://localhost:5174;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:57988;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    # WebSocket support
    location /ws {
        proxy_pass http://localhost:57988;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable the site
sudo ln -s /etc/nginx/sites-available/jaaz /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Troubleshooting

### Common Issues

1. **"Host not allowed" Error**
   - ✅ Fixed: The vite.config.ts now allows all hosts

2. **Cannot connect to backend**
   - Check if port 57988 is open in security groups
   - Verify backend is running: `ps aux | grep python`

3. **Frontend not accessible**
   - Check if port 5174 is open in security groups
   - Verify frontend is running: `ps aux | grep node`

4. **AWS Bedrock access denied**
   - Check AWS credentials configuration
   - Verify IAM permissions for Bedrock
   - Ensure models are enabled in Bedrock console

### Logs and Debugging

```bash
# Check PM2 logs
pm2 logs

# Check individual service logs
pm2 logs jaaz-backend
pm2 logs jaaz-frontend

# Check Nginx logs (if using reverse proxy)
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Service Management

```bash
# PM2 commands
pm2 status          # Check status
pm2 restart all     # Restart all services
pm2 stop all        # Stop all services
pm2 delete all      # Delete all services

# Nginx commands
sudo systemctl status nginx
sudo systemctl restart nginx
sudo systemctl stop nginx
```

## Security Considerations

1. **Firewall**: Configure UFW or iptables for additional security
2. **SSL/TLS**: Use Let's Encrypt for HTTPS in production
3. **Environment Variables**: Store sensitive data in environment variables
4. **Regular Updates**: Keep system and dependencies updated
5. **Monitoring**: Set up CloudWatch or other monitoring solutions

## Performance Optimization

1. **Instance Size**: Use appropriate EC2 instance type for your workload
2. **Storage**: Use SSD storage for better I/O performance
3. **Memory**: Monitor memory usage, especially for large models
4. **Network**: Consider using Elastic Load Balancer for high availability

## Backup and Recovery

1. **Code**: Regular Git commits and backups
2. **Data**: Backup user_data directory regularly
3. **AMI**: Create AMI snapshots of configured instances
4. **Database**: If using external database, ensure regular backups
