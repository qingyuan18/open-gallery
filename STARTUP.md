# Jaaz Application Startup Guide

## Quick Start

### Start the Application
```bash
./start-simple.sh
```

### Stop the Application
```bash
./stop.sh
```

### Stop and Clean Logs
```bash
./stop.sh --clean
```

## What the Scripts Do

### `start-simple.sh`
- **Stops any existing processes** on ports 57988 (backend) and 5174 (frontend)
- **Kills processes by PID files** if they exist
- **Kills processes by name pattern** (python main.py, vite, npm dev)
- **Kills processes by port** as final cleanup
- **Sets up Python virtual environment** if it doesn't exist
- **Installs dependencies** if needed (both Python and Node.js)
- **Starts backend server** on `0.0.0.0:57988`
- **Starts React frontend** on `0.0.0.0:5174`
- **Saves process PIDs** for later cleanup
- **Shows access URLs** and process information

### `stop.sh`
- **Stops processes by PID files** (graceful shutdown)
- **Kills remaining processes by name pattern**
- **Kills processes by port** as backup
- **Cleans up PID files**
- **Optionally cleans log files** with `--clean` flag

## Access URLs

After starting, the application will be available at:
- **Frontend**: `http://your-hostname:5174`
- **Backend**: `http://your-hostname:57988`

## Log Files

- **Backend log**: `backend.log`
- **Frontend log**: `frontend.log`

## Process Information

The scripts save process IDs in:
- **Backend PID**: `backend.pid`
- **Frontend PID**: `frontend.pid`

## Requirements

- **Python 3** with `venv` module
- **Node.js** with `npm`
- **lsof** command (for port checking)

## Troubleshooting

### If ports are still in use:
```bash
# Check what's using the ports
lsof -i :57988
lsof -i :5174

# Kill manually if needed
sudo kill -9 $(lsof -ti:57988)
sudo kill -9 $(lsof -ti:5174)
```

### If dependencies are missing:
```bash
# Backend dependencies
cd server
source venv/bin/activate
pip install -r requirements.txt

# Frontend dependencies
cd react
npm install
```

### If virtual environment is corrupted:
```bash
# Remove and recreate
rm -rf server/venv
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
