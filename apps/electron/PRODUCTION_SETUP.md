# Amazon Automaton - Production Setup

## Quick Start (Recommended)

1. **Run the automated build script:**
   ```bash
   # Windows
   build_and_run.bat
   
   # Or manually:
   npm install
   npm run build
   npm start
   ```

## Manual Setup

### Prerequisites
- Node.js 18+ installed
- Your backend server running on `localhost:4000`

### Step 1: Install Dependencies
```bash
npm install
```

### Step 2: Build the Application
```bash
npm run build
```
This will:
- Build the React app with Vite (optimized and minified)
- Create the Electron executable
- Output files to `dist/` folder

### Step 3: Run the Application
```bash
npm start
```

## Production Features

✅ **Optimized Build:**
- Maximum compression enabled
- Console logs removed in production
- Terser minification
- Single bundle output

✅ **Backend Integration:**
- Connects to `localhost:4000` (IPv4)
- Real-time backend status monitoring
- Native Electron dialogs
- Secure IPC communication

✅ **Cross-Platform:**
- Windows: NSIS installer
- macOS: DMG package
- Linux: AppImage

## File Structure After Build
```
apps/electron/
├── dist/                    # Production build output
│   ├── Amazon Automaton Setup.exe  # Windows installer
│   └── win-unpacked/       # Portable version
├── renderer/               # Built React app
├── main.js                 # Electron main process
├── preload.js             # Secure IPC bridge
└── package.json           # App configuration
```

## Troubleshooting

### Backend Connection Issues
- Ensure backend is running on `localhost:4000`
- Check firewall settings
- Verify IPv4 connectivity

### Build Errors
- Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Update Node.js to latest LTS version
- Check disk space (build requires ~500MB)

### Runtime Errors
- Check Electron console (Ctrl+Shift+I)
- Verify all dependencies are installed
- Ensure backend server is accessible

## Development vs Production

| Feature | Development | Production |
|---------|-------------|------------|
| Hot Reload | ✅ | ❌ |
| Dev Tools | ✅ | ❌ |
| Console Logs | ✅ | ❌ |
| File Size | Large | Optimized |
| Performance | Slower | Faster |

## Backend Requirements

Your backend must have these endpoints:
- `GET http://127.0.0.1:4000/health` - Health check
- `POST http://127.0.0.1:4000/api/submissions` - Form submission

## Security Features

- Context isolation enabled
- Node integration disabled
- Secure IPC communication
- External link protection
- No direct network access from renderer
