"""
Interactive selection utilities for CLI commands.

Provides user-friendly selection prompts for platforms, chains, and campaigns.
"""

import sys
from typing import Any, Dict, Optional

from rich import print as rprint
from rich.console import Console
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from votemarket_toolkit.shared import registry


def format_address(addr: str) -> str:
    """Format address as 0x...abcd"""
    if not addr:
        return "N/A"
    return f"{addr[:6]}...{addr[-4:]}"


def select_chain() -> int:
    """
    Interactive chain selection.

    Returns:
        Selected chain ID
    """
    console = Console()

    # Available chains
    chains = [
        {"id": 1, "name": "Ethereum", "symbol": "ETH"},
        {"id": 42161, "name": "Arbitrum", "symbol": "ARB"},
        {"id": 10, "name": "Optimism", "symbol": "OP"},
        {"id": 137, "name": "Polygon", "symbol": "MATIC"},
        {"id": 8453, "name": "Base", "symbol": "BASE"},
    ]

    rprint("\n[cyan]Select a chain:[/cyan]")
    table = Table(show_header=False, box=None)
    table.add_column("", style="cyan", width=4)
    table.add_column("", style="white")

    for i, chain in enumerate(chains, 1):
        table.add_row(f"[{i}]", f"{chain['name']} ({chain['symbol']})")

    console.print(table)

    while True:
        try:
            choice = IntPrompt.ask(
                "Enter chain number",
                choices=[str(i) for i in range(1, len(chains) + 1)],
            )
            selected_chain = chains[choice - 1]
            rprint(f"[green]✓[/green] Selected: {selected_chain['name']}")
            return selected_chain["id"]
        except (ValueError, IndexError, KeyboardInterrupt):
            rprint("\n[yellow]Selection cancelled[/yellow]")
            sys.exit(0)


def select_platform(
    chain_id: Optional[int] = None, protocol: Optional[str] = None
) -> Dict[str, Any]:
    """
    Interactive platform selection.

    Args:
        chain_id: Filter by chain ID if provided
        protocol: Filter by protocol if provided

    Returns:
        Dictionary with platform info including address, chain_id, protocol, version
    """
    console = Console()

    # Get all platforms
    all_platforms = []
    protocols = ["curve", "balancer", "frax", "fxn", "pendle"]

    for proto in protocols:
        platforms = registry.get_all_platforms(proto)
        for platform in platforms:
            # Apply filters
            if chain_id and platform["chain_id"] != chain_id:
                continue
            if protocol and platform["protocol"] != protocol.lower():
                continue
            all_platforms.append(platform)

    if not all_platforms:
        rprint("[red]No platforms found matching criteria[/red]")
        sys.exit(1)

    # Sort by protocol and chain
    all_platforms.sort(key=lambda x: (x["protocol"], x["chain_id"]))

    # Display platforms
    rprint("\n[cyan]Available VoteMarket Platforms:[/cyan]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Protocol", style="yellow", width=10)
    table.add_column("Chain", style="green", width=12)
    table.add_column("Version", style="blue", width=8)
    table.add_column("Address", style="white")

    chain_names = {
        1: "Ethereum",
        42161: "Arbitrum",
        10: "Optimism",
        137: "Polygon",
        8453: "Base",
    }

    for i, platform in enumerate(all_platforms, 1):
        chain_name = chain_names.get(
            platform["chain_id"], f"Chain {platform['chain_id']}"
        )
        table.add_row(
            str(i),
            platform["protocol"].upper(),
            chain_name,
            platform["version"],
            format_address(platform["address"]),
        )

    console.print(table)

    # Get selection
    while True:
        try:
            choice = IntPrompt.ask(
                "Select platform",
                choices=[str(i) for i in range(1, len(all_platforms) + 1)],
            )
            selected = all_platforms[choice - 1]

            chain_name = chain_names.get(
                selected["chain_id"], f"Chain {selected['chain_id']}"
            )
            rprint(
                f"[green]✓[/green] Selected: {selected['protocol'].upper()} on {chain_name} ({selected['version']})"
            )
            rprint(f"[dim]Address: {selected['address']}[/dim]")

            return selected
        except (ValueError, IndexError, KeyboardInterrupt):
            rprint("\n[yellow]Selection cancelled[/yellow]")
            sys.exit(0)


def select_protocol() -> str:
    """
    Interactive protocol selection.

    Returns:
        Selected protocol name
    """
    console = Console()

    protocols = [
        {"name": "curve", "display": "Curve"},
        {"name": "balancer", "display": "Balancer"},
        {"name": "frax", "display": "Frax"},
        {"name": "fxn", "display": "FXN"},
        {"name": "pendle", "display": "Pendle"},
    ]

    rprint("\n[cyan]Select a protocol:[/cyan]")
    table = Table(show_header=False, box=None)
    table.add_column("", style="cyan", width=4)
    table.add_column("", style="yellow")

    for i, proto in enumerate(protocols, 1):
        table.add_row(f"[{i}]", proto["display"])

    console.print(table)

    while True:
        try:
            choice = IntPrompt.ask(
                "Enter protocol number",
                choices=[str(i) for i in range(1, len(protocols) + 1)],
            )
            selected = protocols[choice - 1]
            rprint(f"[green]✓[/green] Selected: {selected['display']}")
            return selected["name"]
        except (ValueError, IndexError, KeyboardInterrupt):
            rprint("\n[yellow]Selection cancelled[/yellow]")
            sys.exit(0)


async def select_campaign(chain_id: int, platform_address: str) -> int:
    """
    Interactive campaign selection from a platform.

    Args:
        chain_id: Chain ID
        platform_address: Platform address

    Returns:
        Selected campaign ID
    """
    from votemarket_toolkit.campaigns.service import campaign_service

    console = Console()

    # Fetch campaigns
    rprint("[cyan]Fetching campaigns...[/cyan]")
    campaigns = await campaign_service.get_campaigns(
        chain_id=chain_id,
        platform_address=platform_address,
        campaign_id=None,
        check_proofs=False,
    )

    if not campaigns:
        rprint("[red]No campaigns found on this platform[/red]")
        sys.exit(1)

    # Filter to show most relevant (active ones first)
    active = [c for c in campaigns if not c.get("is_closed", False)]
    closed = [c for c in campaigns if c.get("is_closed", False)]

    # Show active campaigns first, then closed
    display_campaigns = active[:20] + closed[:5]  # Limit display

    # Display campaigns
    rprint(
        f"\n[cyan]Campaigns ({len(active)} active, {len(closed)} closed):[/cyan]"
    )
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=4)
    table.add_column("ID", style="yellow", width=6)
    table.add_column("Gauge", style="white", width=12)
    table.add_column("Periods", style="green", width=8)
    table.add_column("Status", style="magenta")

    for i, campaign in enumerate(display_campaigns, 1):
        status = "CLOSED" if campaign.get("is_closed") else "ACTIVE"
        status_style = "dim" if campaign.get("is_closed") else "green"

        table.add_row(
            str(i),
            str(campaign["id"]),
            format_address(campaign["campaign"]["gauge"]),
            str(campaign["campaign"]["number_of_periods"]),
            f"[{status_style}]{status}[/{status_style}]",
        )

    console.print(table)

    if len(campaigns) > len(display_campaigns):
        rprint(
            f"[dim]Showing {len(display_campaigns)} of {len(campaigns)} campaigns[/dim]"
        )

    # Allow direct ID input or selection from list
    rprint("\n[cyan]Enter campaign:[/cyan]")
    rprint(
        "[dim]• Select from list (1-{}) or[/dim]".format(
            len(display_campaigns)
        )
    )
    rprint("[dim]• Enter campaign ID directly[/dim]")

    while True:
        try:
            choice = Prompt.ask("Campaign")

            # Check if it's a list selection
            if choice.isdigit() and 1 <= int(choice) <= len(display_campaigns):
                selected = display_campaigns[int(choice) - 1]
                campaign_id = selected["id"]
            else:
                # Direct ID input
                campaign_id = int(choice)
                # Verify it exists
                if not any(c["id"] == campaign_id for c in campaigns):
                    rprint(f"[red]Campaign #{campaign_id} not found[/red]")
                    continue

            rprint(f"[green]✓[/green] Selected: Campaign #{campaign_id}")
            return campaign_id

        except (ValueError, KeyboardInterrupt):
            rprint("\n[yellow]Selection cancelled[/yellow]")
            sys.exit(0)


def confirm_selection(message: str = "Proceed?") -> bool:
    """
    Ask for confirmation.

    Args:
        message: Confirmation message

    Returns:
        True if confirmed, False otherwise
    """
    response = Prompt.ask(
        f"[yellow]{message}[/yellow]", choices=["y", "n"], default="y"
    )
    return response.lower() == "y"
