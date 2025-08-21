# Amazon Automaton Electron App

This is the Electron version of the Amazon Automaton frontend, providing a native desktop application experience.

## Features

- **Native Desktop App**: Runs as a standalone desktop application
- **Native Dialogs**: Uses system-native error and success dialogs
- **Backend Connection Monitoring**: Real-time status indicator for backend connectivity
- **Enhanced Error Handling**: Better error messages and validation feedback
- **Same Functionality**: All features from the web version are preserved

## Setup

### Prerequisites

- Node.js (v16 or higher)
- npm or yarn
- The backend server running on localhost:4000

### Installation

1. Navigate to the electron directory:
   ```bash
   cd apps/electron
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

### Building for Production

To create a distributable package:

```bash
npm run build
```

This will create platform-specific installers in the `dist` folder.

## Development

### Development Mode

The app runs in development mode with hot reloading:

```bash
npm run dev
```

This will:
- Start the Vite dev server for the renderer process
- Launch Electron with dev tools open
- Enable hot reloading for React components

### Production Mode

To run the built version:

```bash
npm start
```

## Architecture

- **Main Process** (`main.js`): Handles app lifecycle, window management, and IPC
- **Preload Script** (`preload.js`): Provides secure APIs to renderer process
- **Renderer Process** (`src/`): React application with Electron-specific features

## Electron-Specific Features

### Native Dialogs

The app uses Electron's native dialog system instead of browser alerts:
- Error dialogs for validation errors
- Info dialogs for success messages
- Confirmation dialogs for user confirmations

### Backend Connection Monitoring

- Real-time status indicator in the UI
- Automatic connection checking every 30 seconds
- Visual feedback for connection states

### Enhanced Logging

- Console logging through Electron's IPC system
- Better debugging capabilities in development mode

## Backend Integration

The Electron app connects to the same backend as the web version:
- Backend URL: `http://localhost:4000`
- API endpoints remain the same
- All form submissions and data handling identical to web version

## Troubleshooting

### Backend Connection Issues

If the backend status shows as disconnected:
1. Ensure the backend server is running on localhost:4000
2. Check if the backend has the `/api/health` endpoint
3. Verify firewall settings aren't blocking the connection

### Build Issues

If you encounter build problems:
1. Clear node_modules and reinstall: `rm -rf node_modules && npm install`
2. Ensure all dependencies are properly installed
3. Check that electron-builder is properly configured

## Platform Support

- **Windows**: NSIS installer
- **macOS**: DMG package
- **Linux**: AppImage format

## Security

The app follows Electron security best practices:
- Context isolation enabled
- Node integration disabled
- Preload script for secure API exposure
- External link handling through system browser
