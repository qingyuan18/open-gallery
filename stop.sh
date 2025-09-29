#!/bin/bash

# Simple Stop Script for Jaaz Application
# Stops both backend server and React frontend

echo "🛑 Stopping Jaaz Application..."

# Get the current directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to kill process by PID file
kill_by_pidfile() {
    local pidfile=$1
    local service_name=$2
    
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if ps -p $pid > /dev/null 2>&1; then
            echo "🔪 Stopping $service_name (PID: $pid)..."
            kill $pid 2>/dev/null || true
            sleep 2
            if ps -p $pid > /dev/null 2>&1; then
                echo "⚠️  Force killing $service_name..."
                kill -9 $pid 2>/dev/null || true
            fi
            echo "✅ $service_name stopped"
        else
            echo "ℹ️  $service_name was not running"
        fi
        rm -f "$pidfile"
    else
        echo "ℹ️  No PID file found for $service_name"
    fi
}

# Function to kill processes by port
kill_by_port() {
    local port=$1
    local service_name=$2
    
    echo "🔍 Checking port $port..."
    local pids=$(lsof -ti:$port 2>/dev/null || true)
    
    if [ -n "$pids" ]; then
        echo "🔪 Killing $service_name processes on port $port..."
        echo $pids | xargs kill -9 2>/dev/null || true
        echo "✅ Processes on port $port killed"
    else
        echo "ℹ️  No processes found on port $port"
    fi
}

# Stop services using PID files
kill_by_pidfile "$PROJECT_DIR/backend.pid" "Backend"
kill_by_pidfile "$PROJECT_DIR/frontend.pid" "Frontend"

# Kill any remaining processes by name pattern
echo "🔪 Killing any remaining backend processes..."
pkill -f "python.*main.py" 2>/dev/null || true

echo "🔪 Killing any remaining frontend processes..."
pkill -f "vite" 2>/dev/null || true
pkill -f "npm.*dev" 2>/dev/null || true

# Also kill by port as backup
kill_by_port 57988 "Backend"
kill_by_port 5174 "Frontend"

# Clean up log files (optional)
if [ "$1" = "--clean" ]; then
    echo "🧹 Cleaning up log files..."
    rm -f "$PROJECT_DIR/backend.log"
    rm -f "$PROJECT_DIR/frontend.log"
    echo "✅ Log files cleaned"
fi

echo "🎉 Jaaz Application stopped successfully!"
