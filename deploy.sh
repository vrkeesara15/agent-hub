#!/bin/bash
# =================================================================
# Agent Hub - Railway Deployment Script
# =================================================================
# Prerequisites:
#   1. Railway CLI: brew install railway
#   2. Railway account: railway login
#   3. GitHub repo already pushed (done)
# =================================================================

set -e

echo "========================================="
echo "  Agent Hub - Railway Deployment"
echo "========================================="
echo ""

# Check Railway CLI
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Install with: brew install railway"
    exit 1
fi

# Check login
if ! railway whoami &> /dev/null 2>&1; then
    echo "📝 Please log in to Railway first..."
    railway login
fi

echo "✅ Logged in as: $(railway whoami 2>/dev/null)"
echo ""

# -----------------------------------------------------------------
# Step 1: Create Railway project
# -----------------------------------------------------------------
echo "📦 Step 1: Creating Railway project..."
railway init --name agent-hub 2>/dev/null || echo "   (Project may already exist)"
echo ""

# -----------------------------------------------------------------
# Step 2: Deploy Backend
# -----------------------------------------------------------------
echo "🐍 Step 2: Deploying Backend..."
echo "   Setting root directory to apps/backend"

# Create backend service and deploy
cd "$(dirname "$0")/apps/backend"

echo ""
echo "   Please set these environment variables in Railway Dashboard:"
echo "   -----------------------------------------"
echo "   ANTHROPIC_API_KEY = your-api-key-here"
echo "   -----------------------------------------"
echo ""

echo "   Deploying backend..."
railway up --detach 2>&1 || {
    echo ""
    echo "⚠️  If this failed, you may need to:"
    echo "   1. Go to https://railway.app/dashboard"
    echo "   2. Open your 'agent-hub' project"
    echo "   3. Click 'New Service' → 'GitHub Repo' → select 'agent-hub'"
    echo "   4. Set Root Directory = apps/backend"
    echo "   5. Add env var: ANTHROPIC_API_KEY"
}

echo ""
echo "   ⏳ Wait for backend to deploy, then get its URL from the Railway dashboard."
echo "   It will look like: https://agent-hub-backend-production-XXXX.up.railway.app"
echo ""

read -p "   📋 Paste your backend Railway URL here: " BACKEND_URL

# -----------------------------------------------------------------
# Step 3: Deploy Frontend
# -----------------------------------------------------------------
echo ""
echo "🌐 Step 3: Deploying Frontend..."
cd "$(dirname "$0")/apps/web"

echo "   Setting NEXT_PUBLIC_API_URL = $BACKEND_URL"
echo ""

# The user needs to set this in Railway dashboard
echo "   Please set these environment variables in Railway Dashboard for the frontend service:"
echo "   -----------------------------------------"
echo "   NEXT_PUBLIC_API_URL = $BACKEND_URL"
echo "   PORT = 3000"
echo "   -----------------------------------------"
echo ""

railway up --detach 2>&1 || {
    echo ""
    echo "⚠️  If this failed, you may need to:"
    echo "   1. Go to your Railway project dashboard"
    echo "   2. Click 'New Service' → 'GitHub Repo' → select 'agent-hub'"
    echo "   3. Set Root Directory = apps/web"
    echo "   4. Add env var: NEXT_PUBLIC_API_URL = $BACKEND_URL"
}

echo ""
echo "========================================="
echo "  ✅ Deployment Complete!"
echo "========================================="
echo ""
echo "  Backend:  $BACKEND_URL"
echo "  Frontend: Check Railway dashboard for the frontend URL"
echo ""
echo "  Test backend: curl $BACKEND_URL/api/health"
echo ""
