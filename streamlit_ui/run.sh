#!/bin/bash

# Run VoteMarket Toolkit Streamlit UI with UV
# This script should be run from the streamlit_ui directory

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "UV is not installed. Please install it first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Move to the project root directory
cd "$(dirname "$0")/.." || exit

# Run Streamlit with UV
echo "Starting VoteMarket Toolkit Streamlit UI..."
uv run streamlit run streamlit_ui/app.py "$@"