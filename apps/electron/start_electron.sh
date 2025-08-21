#!/bin/bash
echo "Starting Amazon Automaton Electron App..."
echo ""
echo "Make sure the backend server is running on localhost:4000"
echo ""
echo "Starting Vite dev server and Electron..."
cd "$(dirname "$0")"
npm run dev
