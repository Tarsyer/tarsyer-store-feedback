#!/bin/bash
# Deployment script for Store Feedback System
# Run this script on your server to deploy the application

set -e  # Exit on error

echo "🚀 Starting deployment..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}📦 Installing dependencies...${NC}"

# Backend dependencies
# Note: Using existing virtualenv at ~/new created with uv
echo "Installing backend dependencies in ~/new virtualenv..."
source ~/new/bin/activate
cd backend
pip install -r requirements.txt
cd ..

# Frontend dependencies and build
cd frontend
echo "Installing frontend dependencies..."
npm install

echo "Building frontend for production..."
VITE_API_URL=https://store-feedback.tarsyer.com npm run build
cd ..

# Create necessary directories
echo -e "${BLUE}📁 Creating directories...${NC}"
mkdir -p logs
mkdir -p uploads

# Stop existing PM2 processes
echo -e "${BLUE}🛑 Stopping existing services...${NC}"
pm2 delete all 2>/dev/null || true

# Start services with PM2
echo -e "${BLUE}▶️  Starting services...${NC}"
pm2 start ecosystem.config.js

# Save PM2 process list
pm2 save

# Setup PM2 to start on boot (run once)
echo -e "${BLUE}⚙️  Setting up auto-start on boot...${NC}"
pm2 startup systemd -u $USER --hp $HOME || true

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Service status:"
pm2 status
echo ""
echo "View logs with: pm2 logs"
echo "Monitor services: pm2 monit"
echo ""
echo "🌐 Application should be available at: https://store-feedback.tarsyer.com"
