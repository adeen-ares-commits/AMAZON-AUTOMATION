# Quick Start Guide

## Option 1: Automatic Setup (Recommended)

Run the provided script:
- **Windows**: `start_electron.bat`
- **Unix/Mac**: `./start_electron.sh`

This will automatically start both the Vite dev server and Electron.

## Option 2: Manual Setup

If the automatic setup doesn't work, follow these steps:

### Step 1: Install Dependencies
```bash
cd apps/electron
npm install
```

### Step 2: Start Vite Dev Server (Terminal 1)
```bash
npm run dev:vite
```
Wait until you see "Local: http://localhost:5173/"

### Step 3: Start Electron (Terminal 2)
```bash
npm run dev:electron
```

## Troubleshooting

### If you see "ERR_CONNECTION_REFUSED"
This means the Vite dev server isn't running. Make sure to:
1. Start the Vite server first: `npm run dev:vite`
2. Wait for it to be ready (should show "Local: http://localhost:5173/")
3. Then start Electron: `npm run dev:electron`

### If the app shows a blank page
1. Check that the backend is running on localhost:4000
2. Open DevTools (F12) to see any console errors
3. Make sure all dependencies are installed: `npm install`

### Alternative: Build and Run
If development mode doesn't work, try building first:
```bash
npm run build
npm start
```
