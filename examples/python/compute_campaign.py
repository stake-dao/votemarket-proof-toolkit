#!/usr/bin/env python3
"""
Example: Compute optimal campaign parameters for a VoteMarket gauge.

WHAT THIS DOES:
1. Looks at your gauge's historical performance
2. Checks current market rates for similar campaigns
3. Calculates optimal $/vote target (using robust statistics)
4. Figures out max reward per vote that fits your budget

INPUTS YOU PROVIDE:
- Protocol, gauge address, reward token
- Total tokens to distribute
- Campaign duration (weeks)

OUTPUT:
- Max reward per vote (tokens and USD)
- Expected votes
- Budget analysis
- Market positioning
"""

import asyncio
from rich import print as rprint

from votemarket_toolkit.analytics import get_campaign_optimizer


async def main():
    # ═══════════════════════════════════════════════════
    # CONFIGURATION - Edit these values
    # ═══════════════════════════════════════════════════
    protocol = "curve"
    gauge = "0xB84637aB9Be835580821A67823f414FFd0bbf625"  # SDT/WETH
    reward_token = "0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F"  # SDT
    chain_id = 1  # Ethereum mainnet

    total_reward_tokens = 10000.0  # Your budget
    duration_weeks = 2  # Campaign length

    # ═══════════════════════════════════════════════════
    # Optional: Advanced tuning (leave as defaults unless you know what you're doing)
    # ═══════════════════════════════════════════════════
    # market_percentile = 0.70  # Target 70th percentile (competitive but not extreme)
    # ema_alpha = 0.3           # Smoothing (30% weight to recent data)
    # mad_multiplier = 0.5      # Safety margin (0.5 * MAD above target)
    # min_ppv_usd = 0.0001      # Minimum $/vote floor
    # max_ppv_usd = 1.0         # Maximum $/vote ceiling
    # efficiency_floor = 1.05   # Require 5% minimum efficiency

    rprint(f"\n[cyan]Computing optimal parameters for gauge {gauge}...[/cyan]\n")

    optimizer = get_campaign_optimizer()

    try:
        # Calculate optimal campaign parameters
        # Uses robust statistics: percentile (70th), EMA smoothing, MAD margin
        result = await optimizer.calculate_optimal_campaign(
            protocol=protocol,
            gauge=gauge,
            reward_token=reward_token,
            chain_id=chain_id,
            total_reward_tokens=total_reward_tokens,
            default_duration_weeks=duration_weeks,
            # All other parameters use sensible defaults
        )

        # ═══ Display Results ═══
        rprint(f"[bold]Token Price:[/bold] ${result.token_price:.4f}")
        rprint(f"[bold]Total Budget:[/bold] {result.total_reward_tokens:,.2f} tokens (${result.total_reward_tokens * result.token_price:,.2f})")

        # Historical performance (smoothed with EMA)
        rprint(f"\n[yellow]Your Historical Performance:[/yellow]")
        rprint(f"  • Avg $/vote: ${result.avg_dollar_per_vote:.6f} (EMA smoothed)")
        rprint(f"  • Avg efficiency: {result.avg_efficiency:.2f}%")
        rprint(f"  • Avg votes: {result.avg_votes:.0f}")

        # Market comparison
        rprint(f"\n[yellow]Market Comparison:[/yellow]")
        rprint(f"  • Total active campaigns: {result.total_active_campaigns}")
        rprint(f"  • Comparable peers (same chain): {result.total_peer_campaigns}")
        rprint(f"  • Market target (70th percentile + safety): ${result.market_percentile_target:.6f}/vote")
        if result.peer_median_dollar_per_vote:
            rprint(f"  • Peer median: ${result.peer_median_dollar_per_vote:.6f}/vote")

        # Recommended campaign parameters
        params = result.parameters
        rprint(f"\n[green]═══ Recommended Campaign Setup ═══[/green]")

        rprint(f"\n[bold]Max Reward Per Vote:[/bold]")
        rprint(f"  • {params.max_reward_per_vote_tokens:.6f} tokens/vote")
        rprint(f"  • ${params.max_reward_per_vote_usd:.6f}/vote")
        if params.budget_shortfall_pct > 0:
            rprint(f"  • [yellow]Note: Adjusted down {params.budget_shortfall_pct:.1f}% to fit budget[/yellow]")

        rprint(f"\n[bold]Expected Votes:[/bold] {params.votes_expected:.0f} votes/period")

        rprint(f"\n[bold]Campaign Duration:[/bold] {params.duration_weeks} weeks")
        rprint(f"  • Per week: {params.reward_per_period_tokens:,.2f} tokens (${params.reward_per_period_usd:,.2f})")
        rprint(f"  • Total: {result.total_reward_tokens:,.2f} tokens (${result.total_reward_tokens * result.token_price:,.2f})")

        # Warnings & recommendations (if any)
        if params.warnings or params.recommendations:
            rprint(f"\n[yellow]Notes:[/yellow]")
            for warning in params.warnings:
                rprint(f"  ⚠ {warning}")
            for rec in params.recommendations:
                rprint(f"  💡 {rec}")

        # Market positioning
        pos = result.positioning
        rprint(f"\n[cyan]═══ How You Compare ═══[/cyan]")
        rprint(f"Top {pos.percentile:.0f}% of {pos.peer_count} similar campaigns on {['Ethereum'][0] if chain_id == 1 else f'chain {chain_id}'}")

        if pos.pct_vs_peer_median is not None:
            if pos.pct_vs_peer_median > 0:
                rprint(f"[green]✓ {abs(pos.pct_vs_peer_median):.1f}% above peer median[/green]")
            else:
                rprint(f"[dim]{abs(pos.pct_vs_peer_median):.1f}% below peer median[/dim]")

    finally:
        await optimizer.close()


if __name__ == "__main__":
    asyncio.run(main())
