# Amazon Automaton Electron App Setup Guide

## Quick Start

### Prerequisites
- Node.js (v16 or higher)
- npm or yarn
- Backend server running on localhost:4000

### Installation Steps

1. **Navigate to the electron directory:**
   ```bash
   cd apps/electron
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```

   Or use the provided scripts:
   - Windows: `start_electron.bat`
   - Unix/Mac: `./start_electron.sh`

## What's Different from the Web Version

### Enhanced Features
- **Native Desktop App**: Runs as a standalone application
- **Native Dialogs**: System-native error and success messages
- **Backend Connection Monitoring**: Real-time status indicator
- **Enhanced Error Handling**: Better validation feedback
- **Improved Logging**: Console output through Electron's IPC

### Backend Integration
- Connects to the same backend as the web version
- Backend URL: `http://localhost:4000`
- All API endpoints remain identical
- Form submissions work exactly the same

### Electron-Specific Features

#### Native Dialogs
Instead of browser alerts, the app uses:
- **Error dialogs** for validation errors
- **Info dialogs** for success messages
- **Confirmation dialogs** for user confirmations

#### Backend Status Indicator
- Real-time connection status in the UI header
- Visual indicators (green/yellow/red)
- Automatic checking every 30 seconds
- Error details displayed when disconnected

#### Enhanced Logging
- Console logs go through Electron's IPC system
- Better debugging in development mode
- Fallback to regular console when not in Electron

## Development Workflow

### Development Mode
```bash
npm run dev
```
This will:
- Start Vite dev server for the renderer process
- Launch Electron with dev tools open
- Enable hot reloading for React components

### Production Build
```bash
npm run build
```
This creates platform-specific installers in the `dist` folder.

### Running Built Version
```bash
npm start
```

## File Structure

```
apps/electron/
├── main.js              # Main Electron process
├── preload.js           # Preload script for secure APIs
├── package.json         # Dependencies and scripts
├── vite.config.js       # Vite configuration
├── tailwind.config.js   # Tailwind CSS configuration
├── postcss.config.js    # PostCSS configuration
├── src/
│   ├── index.html       # Main HTML file
│   ├── main.jsx         # React entry point
│   ├── App.jsx          # Main React component
│   └── index.css        # Global styles
├── start_electron.bat   # Windows startup script
├── start_electron.sh    # Unix startup script
├── README.md           # General documentation
└── SETUP.md            # This setup guide
```

## Troubleshooting

### Common Issues

#### Backend Connection Problems
**Symptoms**: Status shows "disconnected" or "checking"
**Solutions**:
1. Ensure backend server is running on localhost:4000
2. Check if backend has `/api/health` endpoint
3. Verify firewall settings
4. Try restarting both backend and Electron app

#### Build Issues
**Symptoms**: npm install or build fails
**Solutions**:
1. Clear node_modules: `rm -rf node_modules && npm install`
2. Update Node.js to v16 or higher
3. Check for conflicting global packages
4. Verify all dependencies are properly installed

#### Development Server Issues
**Symptoms**: App doesn't load or shows errors
**Solutions**:
1. Check if port 5173 is available
2. Restart the development server
3. Clear browser cache if testing in browser
4. Check console for specific error messages

### Platform-Specific Notes

#### Windows
- Use `start_electron.bat` for easy startup
- Ensure Windows Defender doesn't block the app
- Run as administrator if needed for file access

#### macOS
- Use `./start_electron.sh` for easy startup
- Grant necessary permissions when prompted
- May need to allow app in Security & Privacy settings

#### Linux
- Use `./start_electron.sh` for easy startup
- Ensure proper permissions: `chmod +x start_electron.sh`
- May need additional dependencies for GUI

## Security Features

The Electron app follows security best practices:
- **Context isolation** enabled
- **Node integration** disabled
- **Preload script** for secure API exposure
- **External links** handled through system browser
- **No remote code execution** allowed

## API Reference

### Electron APIs Available in Renderer

```javascript
// Dialog APIs
window.electronAPI.showErrorDialog(title, content)
window.electronAPI.showInfoDialog(title, content)
window.electronAPI.showConfirmationDialog(title, content)

// Backend connection check
window.electronAPI.checkBackendStatus()

// Platform info
window.electronAPI.platform
window.electronAPI.appVersion

// Console logging
window.electronConsole.log(...args)
window.electronConsole.error(...args)
window.electronConsole.warn(...args)
window.electronConsole.info(...args)
```

## Migration from Web Version

The Electron app is designed to be a drop-in replacement for the web version:

1. **Same UI**: Identical visual design and layout
2. **Same Functionality**: All features work exactly the same
3. **Same Backend**: Uses identical API endpoints
4. **Enhanced UX**: Better error handling and feedback
5. **Native Experience**: Desktop app feel with native dialogs

## Support

For issues specific to the Electron app:
1. Check this setup guide
2. Review the README.md file
3. Check console logs for error details
4. Verify backend connectivity
5. Test with the web version to isolate issues
