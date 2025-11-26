"""Shared formatting and file utilities for commands."""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from rich.console import Console
from rich.table import Table

# Shared console instance
console = Console()


def load_json(file_path: str) -> Dict[str, Any]:
    """
    Load and parse a JSON file.

    Supports both package resources (when installed) and local file paths (for development).

    Args:
        file_path: Path to JSON file (can be relative package path or absolute)

    Returns:
        Parsed JSON data as dictionary
    """
    # Check if this looks like a package resource path
    if file_path.startswith("votemarket_toolkit/"):
        # Convert path to package notation
        parts = file_path.split("/")
        package = ".".join(
            parts[:-1]
        )  # e.g., "votemarket_toolkit.resources.abi"
        resource = parts[-1]  # e.g., "ccip_adapter.json"

        # Use importlib.resources for Python 3.9+
        if sys.version_info >= (3, 9):
            from importlib.resources import files

            resource_path = files(package).joinpath(resource)
            return json.loads(resource_path.read_text())
        else:
            # Fallback for Python 3.7-3.8
            from importlib.resources import read_text

            return json.loads(read_text(package, resource))

    # Fall back to regular file opening for absolute paths
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


def format_closability_display(closability: Dict[str, Any]) -> str:
    """
    Format closability info for Rich table display.

    Args:
        closability: Dict with is_closable, can_be_closed_by, closability_status

    Returns:
        Rich-formatted string for display
    """
    if closability["is_closable"]:
        if closability["can_be_closed_by"] == "Anyone":
            match = re.search(r"(\d+)d", closability["closability_status"])
            days = match.group(1) if match else "?"
            return f"[bold yellow]Anyone ({days}d)[/bold yellow]"
        else:
            match = re.search(r"(\d+)d", closability["closability_status"])
            days = match.group(1) if match else "?"
            return f"[cyan]Manager ({days}d)[/cyan]"
    elif "Active" in closability["closability_status"]:
        match = re.search(r"(\d+)d", closability["closability_status"])
        days = match.group(1) if match else "?"
        return f"[green]Active ({days}d)[/green]"
    elif "Claim Period" in closability["closability_status"]:
        match = re.search(r"(\d+)d", closability["closability_status"])
        days = match.group(1) if match else "?"
        return f"[dim]Claim ({days}d)[/dim]"
    else:
        return f"[dim]{closability['closability_status'][:20]}[/dim]"


def create_campaigns_table() -> Table:
    """
    Create a Rich table with standard campaign columns.

    Returns:
        Configured Rich Table for campaign display
    """
    table = Table(
        show_header=True,
        header_style="bold cyan",
        show_lines=False,
        pad_edge=False,
        box=None,
    )
    table.add_column("ID", width=4, justify="right")
    table.add_column("Gauge", width=12)
    table.add_column("Token", width=12)
    table.add_column("Status", width=10, justify="center")
    table.add_column("Periods", width=8, justify="center")
    table.add_column("Total", width=10, justify="right")
    table.add_column("Closable", width=22)
    return table


def add_campaign_to_table(
    table: Table,
    campaign: Dict[str, Any],
    status: str,
    closability: Dict[str, Any],
) -> None:
    """
    Add a campaign row to the campaigns table.

    Args:
        table: Rich Table to add row to
        campaign: Campaign data dict
        status: Campaign status string
        closability: Closability info dict
    """
    total_reward = f"{campaign['campaign']['total_reward_amount'] / 1e18:.2f}"

    updated_periods = sum(
        1 for p in campaign.get("periods", []) if p["updated"]
    )
    total_periods = len(campaign.get("periods", []))
    periods_display = f"{updated_periods}/{total_periods}"

    closable_display = format_closability_display(closability)

    table.add_row(
        str(campaign["id"]),
        format_address(campaign["campaign"]["gauge"]),
        format_address(campaign["campaign"]["reward_token"]),
        status,
        periods_display,
        total_reward[:10],
        closable_display,
    )
