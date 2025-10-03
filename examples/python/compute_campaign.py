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
    protocol = "curve"
    gauge = "0xB84637aB9Be835580821A67823f414FFd0bbf625"  # SDT/WETH
    reward_token = "0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F"  # SDT
    chain_id = 1  # Ethereum mainnet

    total_reward_tokens = 30_000
    duration_weeks = 2  # Campaign length

    # ═══════════════════════════════════════════════════
    # Optional: Advanced tuning
    # ═══════════════════════════════════════════════════
    # market_percentile = 0.70  # Target 70th percentile (competitive but not extreme)
    # ema_alpha = 0.3           # Smoothing (30% weight to recent data)
    # mad_multiplier = 0.5      # Safety margin (0.5 * MAD above target)
    # min_ppv_usd = 0.0001      # Minimum $/vote floor
    # max_ppv_usd = 1.0         # Maximum $/vote ceiling
    # efficiency_floor = 1.05   # Require 5% minimum efficiency

    rprint(
        f"\n[cyan]Computing optimal parameters for gauge {gauge}...[/cyan]\n"
    )

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
        )

        # ═══ Display Results ═══
        rprint(f"[bold]Token Price:[/bold] ${result.token_price:.4f}")
        rprint(
            f"[bold]Your Budget:[/bold] {result.total_budget:,.0f} tokens (${result.total_budget * result.token_price:,.2f})"
        )

        # Historical performance (smoothed with EMA)
        rprint("\n[yellow]Your Historical Performance:[/yellow]")
        rprint(
            f"  • Avg $/vote: ${result.historical_dpv_usd:.6f} (EMA smoothed)"
        )
        rprint(f"  • Avg efficiency: {result.efficiency_expected:.2f}%")
        rprint(f"  • Avg votes: {result.historical_votes:.0f}")

        # Market comparison
        rprint("\n[yellow]Market Comparison:[/yellow]")
        rprint(f"  • Comparable peers (same chain): {result.peer_count}")
        rprint(
            f"  • Market target (70th percentile + safety): ${result.market_target_usd:.6f}/vote"
        )
        if result.peer_median_usd:
            rprint(f"  • Peer median: ${result.peer_median_usd:.6f}/vote")

        # Recommended campaign parameters
        rprint("\n[green]═══ Recommended Campaign Setup ═══[/green]")

        rprint("\n[bold]Max Reward Per Vote:[/bold]")
        rprint(f"  • {result.max_reward_per_vote_tokens:.6f} tokens/vote")
        rprint(f"  • ${result.max_reward_per_vote_usd:.6f}/vote")

        rprint(
            f"\n[bold]Expected Votes:[/bold] {result.votes_expected:.0f} votes/period"
        )

        # Budget analysis - show what's actually needed
        rprint("\n[bold]Budget Analysis:[/bold]")
        rprint(f"  • Your budget: {result.total_budget:,.0f} tokens")
        rprint(
            f"  • Tokens needed: {result.tokens_needed:,.0f} tokens to achieve ${result.max_reward_per_vote_usd:.6f}/vote"
        )

        if result.budget_surplus_pct > 0:
            excess = result.total_budget - result.tokens_needed
            rprint(
                f"  • [yellow]⚠ Over-budgeted by {result.budget_surplus_pct:.0f}%[/yellow]"
            )
            rprint(
                f"  • [dim]Excess: {excess:,.0f} tokens won't be distributed[/dim]"
            )
            rprint(
                f"\n  💡 You can reduce budget to {result.tokens_needed:,.0f} tokens to save {excess:,.0f} tokens"
            )
        elif result.budget_shortfall_pct > 0:
            shortage = result.tokens_needed - result.total_budget
            rprint(
                f"  • [yellow]⚠ Under-budgeted by {result.budget_shortfall_pct:.0f}%[/yellow]"
            )
            rprint(f"  • [dim]Short: {shortage:,.0f} tokens[/dim]")
            rprint(
                f"\n  💡 Increase budget to {result.tokens_needed:,.0f} tokens to achieve market target"
            )
        else:
            rprint("  • [green]✓ Budget is perfect for target[/green]")

        rprint(
            f"\n[bold]Campaign Duration:[/bold] {result.duration_weeks} weeks"
        )
        per_week = result.tokens_needed / result.duration_weeks
        rprint(f"  • Per week: {per_week:,.0f} tokens")

        # Market positioning
        rprint("\n[cyan]═══ How You Compare ═══[/cyan]")
        chain_name = "Ethereum" if chain_id == 1 else f"Chain {chain_id}"
        rprint(f"{result.peer_count} comparable campaigns on {chain_name}")

        if result.pct_above_peer_median is not None:
            if result.pct_above_peer_median > 0:
                rprint(
                    f"[green]✓ {abs(result.pct_above_peer_median):.1f}% above peer median[/green]"
                )
            else:
                rprint(
                    f"[dim]{abs(result.pct_above_peer_median):.1f}% below peer median[/dim]"
                )

    finally:
        await optimizer.close()


if __name__ == "__main__":
    asyncio.run(main())
