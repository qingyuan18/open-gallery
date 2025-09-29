#!/bin/bash

# Simple Startup Script for Jaaz Application
# Starts both backend server and React frontend
# Note: Uses current conda environment for Python dependencies

set -e

echo "🚀 Starting Jaaz Application (Simple Mode)..."

# Check conda environment
if [ -n "$CONDA_DEFAULT_ENV" ]; then
    echo "🐍 Using conda environment: $CONDA_DEFAULT_ENV"
else
    echo "⚠️  Warning: No conda environment detected. Make sure you're in the correct environment."
fi

# Get the current directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Project directory: $PROJECT_DIR"

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  Port $port is already in use"
        return 1
    else
        echo "✅ Port $port is available"
        return 0
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    echo "🔪 Killing processes on port $port..."
    lsof -ti:$port | xargs kill -9 2>/dev/null || true
    sleep 2
}

# Stop existing processes
echo "🛑 Stopping existing processes..."

# Kill processes by PID files if they exist
if [ -f "$PROJECT_DIR/backend.pid" ]; then
    BACKEND_PID=$(cat "$PROJECT_DIR/backend.pid")
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo "🔪 Stopping backend process (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null || true
        sleep 2
        # Force kill if still running
        if ps -p $BACKEND_PID > /dev/null 2>&1; then
            kill -9 $BACKEND_PID 2>/dev/null || true
        fi
    fi
    rm -f "$PROJECT_DIR/backend.pid"
fi

if [ -f "$PROJECT_DIR/frontend.pid" ]; then
    FRONTEND_PID=$(cat "$PROJECT_DIR/frontend.pid")
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo "🔪 Stopping frontend process (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null || true
        sleep 2
        # Force kill if still running
        if ps -p $FRONTEND_PID > /dev/null 2>&1; then
            kill -9 $FRONTEND_PID 2>/dev/null || true
        fi
    fi
    rm -f "$PROJECT_DIR/frontend.pid"
fi

# Kill any remaining processes by name pattern
echo "🔪 Killing any remaining backend processes..."
pkill -f "python.*main.py" 2>/dev/null || true

echo "🔪 Killing any remaining frontend processes..."
pkill -f "vite" 2>/dev/null || true
pkill -f "npm.*dev" 2>/dev/null || true

# Kill processes by port as final cleanup
if ! check_port 57988; then
    kill_port 57988
fi

if ! check_port 5174; then
    kill_port 5174
fi

# Wait a moment for cleanup
sleep 3

# Start backend
echo "🔧 Starting backend server..."
cd "$PROJECT_DIR/server"
echo "📁 Current directory: $(pwd)"

# Check Python environment
echo "� Using Python: $(which python)"
echo "🐍 Python version: $(python --version)"

# Install dependencies if needed (using current conda environment)
if [ ! -f ".deps_installed" ]; then
    echo "📦 Installing Python dependencies..."
    pip install -r requirements.txt
    touch .deps_installed
fi

# Start backend in background
echo "🚀 Starting backend on 0.0.0.0:57988..."
nohup python main.py --port 57988 > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ Backend started with PID: $BACKEND_PID"

# Start frontend
echo "🔧 Starting frontend server..."
cd "$PROJECT_DIR/react"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    npm install
fi

# Start frontend in background
echo "🚀 Starting frontend on 0.0.0.0:5174..."
nohup npm run dev:ec2 > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "✅ Frontend started with PID: $FRONTEND_PID"

# Save PIDs for later cleanup
echo $BACKEND_PID > "$PROJECT_DIR/backend.pid"
echo $FRONTEND_PID > "$PROJECT_DIR/frontend.pid"

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 5

# Check if services are running
echo "🔍 Checking services..."

if ps -p $BACKEND_PID > /dev/null; then
    echo "✅ Backend is running (PID: $BACKEND_PID)"
else
    echo "❌ Backend failed to start"
    echo "📄 Backend log:"
    cat "$PROJECT_DIR/backend.log"
    exit 1
fi

if ps -p $FRONTEND_PID > /dev/null; then
    echo "✅ Frontend is running (PID: $FRONTEND_PID)"
else
    echo "❌ Frontend failed to start"
    echo "📄 Frontend log:"
    cat "$PROJECT_DIR/frontend.log"
    exit 1
fi

# Get EC2 public information
echo "🌐 Getting access information..."
PUBLIC_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/public-hostname 2>/dev/null || echo "localhost")
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "127.0.0.1")

echo ""
echo "🎉 Jaaz Application Started Successfully!"
echo "================================================"
echo "📍 Access URLs:"
echo "   Frontend: http://$PUBLIC_HOSTNAME:5174"
echo "   Backend:  http://$PUBLIC_HOSTNAME:57988"
echo ""
if [ "$PUBLIC_IP" != "127.0.0.1" ]; then
    echo "   Alternative (IP):"
    echo "   Frontend: http://$PUBLIC_IP:5174"
    echo "   Backend:  http://$PUBLIC_IP:57988"
    echo ""
fi
echo "📋 Process Information:"
echo "   Backend PID:  $BACKEND_PID"
echo "   Frontend PID: $FRONTEND_PID"
echo ""
echo "📄 Log Files:"
echo "   Backend:  $PROJECT_DIR/backend.log"
echo "   Frontend: $PROJECT_DIR/frontend.log"
echo ""
echo "🛑 To stop services, run: ./stop.sh"
echo "================================================"
