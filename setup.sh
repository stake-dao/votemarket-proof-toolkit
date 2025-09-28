#!/bin/bash
# Setup script for VoteMarket Toolkit

echo "🚀 Setting up VoteMarket Toolkit..."
echo ""

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "✅ UV installed!"
    echo ""
fi

echo "📦 UV version: $(uv --version)"
echo ""

# Install Python and sync dependencies
echo "🐍 Installing Python and dependencies..."
uv python install 3.12
uv sync
echo ""

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📄 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your RPC endpoints!"
    echo ""
fi

# Test installation
echo "🧪 Testing installation..."
if uv run -c "import votemarket_toolkit; print('✅ VoteMarket Toolkit ready!')"; then
    echo ""
    echo "🎉 Setup complete! Run commands with:"
    echo ""
    echo "  uv run examples/python/using_registry.py"
    echo "  uv run examples/python/get_campaign.py curve 97"
    echo ""
else
    echo "❌ Setup failed."
    exit 1
fi