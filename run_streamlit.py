#!/usr/bin/env python3
"""Run the VoteMarket Toolkit Streamlit UI application."""

import sys
import subprocess
from pathlib import Path

def main():
    """Run the Streamlit app."""
    # Get the path to the Streamlit app
    app_path = Path(__file__).parent / "streamlit_ui" / "app.py"
    
    # Build the command
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    
    # Add any additional arguments passed to this script
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    # Run Streamlit
    subprocess.run(cmd)

if __name__ == "__main__":
    main()