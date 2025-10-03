"""Shared formatting and file utilities for commands."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from rich.console import Console

# Shared console instance
console = Console()


def load_json(file_path: str) -> Dict[str, Any]:
    """
    Load and parse a JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data as dictionary
    """
    with open(file_path, "r") as file:
        return json.load(file)


def format_address(address: str, length: int = 10) -> str:
    """
    Format an Ethereum address to show first and last characters.

    Args:
        address: Ethereum address
        length: Total visible characters (default: 10)

    Returns:
        Formatted address like "0x1234...5678"
    """
    if not address:
        return "N/A"
    if len(address) <= length:
        return address
    return f"{address[:6]}...{address[-4:]}"


def format_timestamp(
    timestamp: int, format_str: str = "%Y-%m-%d %H:%M"
) -> str:
    """
    Format a Unix timestamp to a readable date string.

    Args:
        timestamp: Unix timestamp
        format_str: strftime format string

    Returns:
        Formatted date string
    """
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime(format_str)


def save_json_output(
    data: Dict[str, Any],
    filename: str,
    output_dir: str = "output",
    print_path: bool = True,
) -> str:
    """
    Save data to a JSON file with automatic directory creation.

    Args:
        data: Data to save
        filename: Output filename (can include subdirectories)
        output_dir: Base output directory (default: 'output')
        print_path: Whether to print the saved file path

    Returns:
        Full path to saved file
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filepath = output_path / filename

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    if print_path:
        console.print(f"[cyan]Data saved to:[/cyan] {filepath}")

    return str(filepath)


def generate_timestamped_filename(prefix: str, extension: str = "json") -> str:
    """
    Generate a filename with timestamp.

    Args:
        prefix: Filename prefix
        extension: File extension (without dot)

    Returns:
        Filename like "prefix_20240315_123456.json"
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"
