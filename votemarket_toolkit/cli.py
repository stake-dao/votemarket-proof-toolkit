#!/usr/bin/env python3
"""
Unified CLI for VoteMarket Toolkit.

Examples:
  - Proofs
    votemarket proofs-user --protocol curve --gauge-address 0x... --user-address 0x... --block-number 18500000
    votemarket proofs-gauge --protocol curve --gauge-address 0x... --current-epoch 1699920000 --block-number 18500000

  - Campaigns
    votemarket campaigns-active --protocol curve --chain-id 42161
    votemarket campaigns-active --platform 0x... --chain-id 42161

  - User eligibility
    votemarket users-eligibility --user 0x... --protocol curve [--gauge 0x...] [--chain-id 42161]

  - Index votes
    votemarket index-votes --protocol curve --gauge-address 0x... [--chain-id 1]

  - User campaign status
    votemarket user-campaign-status --chain-id 42161 --platform 0x... --campaign-id 97 --user 0x...
"""

import argparse
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from eth_utils import to_checksum_address

from votemarket_toolkit.campaigns.service import (
    CampaignService,
    campaign_service,
)
from votemarket_toolkit.commands.validation import (
    validate_chain_id,
    validate_eth_address,
    validate_protocol,
)
from votemarket_toolkit.proofs import UserEligibilityService, VoteMarketProofs
from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.utils.formatters import (
    console,
    format_address,
    generate_timestamped_filename,
    save_json_output,
)
from votemarket_toolkit.votes.services.votes_service import votes_service


def _resolve_platform_from_protocol(
    protocol: str, chain_id: int
) -> Optional[str]:
    """Resolve a platform address for a protocol/chain, trying v2→v2_old→v1."""
    for version in ("v2", "v2_old", "v1"):
        addr = registry.get_platform(protocol, chain_id, version)
        if addr:
            return addr
    return None


def cmd_block_info(args: argparse.Namespace) -> None:
    chain_id = args.chain_id
    validate_chain_id(chain_id)

    vm = VoteMarketProofs(chain_id)
    info = vm.get_block_info(args.block_number)

    out = {
        "block_number": info["block_number"],
        "block_hash": info["block_hash"],
        "block_timestamp": info["block_timestamp"],
        "rlp_block_header": info["rlp_block_header"],
    }

    filename = args.output or f"block_info_{args.block_number}.json"
    save_json_output(out, filename)

    console.print(
        f"Saved block info for block {args.block_number} → output/{filename}"
    )


def cmd_proofs_user(args: argparse.Namespace) -> None:
    protocol = validate_protocol(args.protocol)
    gauge_address = validate_eth_address(args.gauge_address, "gauge_address")
    user_address = validate_eth_address(args.user_address, "user_address")
    chain_id = args.chain_id
    validate_chain_id(chain_id)

    vm = VoteMarketProofs(chain_id)
    user_proof = vm.get_user_proof(
        protocol, gauge_address, user_address, args.block_number
    )

    output_data = {
        "protocol": protocol,
        "gauge_address": gauge_address,
        "user_address": to_checksum_address(user_address),
        "block_number": args.block_number,
        "storage_proof": "0x" + user_proof["storage_proof"].hex(),
    }
    filename = args.output or f"user_proof_{args.block_number}.json"
    save_json_output(output_data, filename)

    console.print(f"User proof generated. Saved → output/{filename}")


def cmd_proofs_gauge(args: argparse.Namespace) -> None:
    protocol = validate_protocol(args.protocol)
    gauge_address = validate_eth_address(args.gauge_address, "gauge_address")
    chain_id = args.chain_id
    validate_chain_id(chain_id)

    vm = VoteMarketProofs(chain_id)
    gauge_proof = vm.get_gauge_proof(
        protocol, gauge_address, args.current_epoch, args.block_number
    )

    output_data = {
        "protocol": protocol,
        "gauge_address": gauge_address,
        "current_epoch": args.current_epoch,
        "block_number": args.block_number,
        "gauge_controller_proof": "0x"
        + gauge_proof["gauge_controller_proof"].hex(),
        "point_data_proof": "0x" + gauge_proof["point_data_proof"].hex(),
    }
    filename = args.output or f"gauge_proof_{args.block_number}.json"
    save_json_output(output_data, filename)

    console.print(f"Gauge proof generated. Saved → output/{filename}")


async def _fetch_active_campaigns(
    args: argparse.Namespace,
) -> List[Dict[str, Any]]:
    service = CampaignService()

    if args.platform:
        campaigns = await service.get_active_campaigns(
            chain_id=args.chain_id,
            platform_address=args.platform,
            campaign_id=args.campaign_id,
            check_proofs=bool(args.check_proofs),
        )
        return campaigns

    if not args.protocol or not args.chain_id:
        raise ValueError(
            "Provide either --platform and --chain-id, or --protocol and --chain-id"
        )

    protocol = validate_protocol(args.protocol)
    platform = _resolve_platform_from_protocol(protocol, args.chain_id)
    if not platform:
        raise ValueError(
            f"No platform found for {protocol} on chain {args.chain_id}"
        )

    campaigns = await service.get_active_campaigns(
        chain_id=args.chain_id,
        platform_address=platform,
        campaign_id=args.campaign_id,
        check_proofs=bool(args.check_proofs),
    )
    return campaigns


def cmd_campaigns_active(args: argparse.Namespace) -> None:
    async def run():
        campaigns = await _fetch_active_campaigns(args)
        console.print(f"Active campaigns: {len(campaigns)}")

        if args.json:
            filename = args.output or generate_timestamped_filename(
                "active_campaigns"
            )
            save_json_output({"campaigns": campaigns}, filename)
            return

        # Simple tabular text output
        for c in campaigns:
            cid = c.get("id")
            gauge = c.get("campaign", {}).get("gauge", "")
            manager = c.get("campaign", {}).get("manager", "")
            rem = c.get("remaining_periods", 0)
            console.print(
                f"- Campaign #{cid} | gauge {gauge[:10]}... | manager {manager[:10]}... | remaining {rem}"
            )

    asyncio.run(run())


def cmd_users_eligibility(args: argparse.Namespace) -> None:
    async def run():
        user = validate_eth_address(args.user, "user")
        protocol = validate_protocol(args.protocol)
        gauge = (
            validate_eth_address(args.gauge, "gauge") if args.gauge else None
        )

        async with UserEligibilityService() as service:  # type: ignore
            results = await service.check_user_eligibility(
                user=user,
                protocol=protocol,
                chain_id=args.chain_id,
                gauge_address=gauge,
                status_filter=args.status,
            )

        if args.json:
            filename = args.output or generate_timestamped_filename(
                "user_eligibility"
            )
            save_json_output(results, filename)
            return

        # Print concise summary
        summary = results.get("summary", {})
        console.print("Eligibility Summary:")
        console.print(
            f"  Checked: {summary.get('total_campaigns_checked', 0)} campaigns"
        )
        console.print(
            f"  With eligibility: {summary.get('campaigns_with_eligibility', 0)}"
        )
        console.print(
            f"  Claimable periods: {summary.get('total_claimable_periods', 0)}"
        )

        # Minimal per-chain display
        chains = results.get("chains", {})
        for chain_id, data in chains.items():
            console.print(f"\nChain {chain_id}:")
            for c in data.get("campaigns", []):
                status = "ACTIVE" if not c.get("is_closed") else "CLOSED"
                console.print(
                    f"  - Campaign #{c.get('id')} [{status}] gauge {c.get('gauge')[:10]}..."
                )

    asyncio.run(run())


def cmd_index_votes(args: argparse.Namespace) -> None:
    """Index and display votes for a gauge."""

    async def run():
        protocol = validate_protocol(args.protocol)
        gauge_address = validate_eth_address(
            args.gauge_address, "gauge_address"
        )
        chain_id = args.chain_id
        validate_chain_id(chain_id)

        web3_service = Web3Service.get_instance(chain_id)
        block_number = web3_service.get_latest_block()["number"]

        gauge_votes = await votes_service.get_gauge_votes(
            protocol, gauge_address, block_number
        )

        if args.json:
            output = {
                "protocol": protocol,
                "gauge_address": gauge_address,
                "chain_id": chain_id,
                "latest_block": gauge_votes.latest_block,
                "votes": [
                    {
                        "time": v.time,
                        "user": v.user,
                        "weight": v.weight,
                    }
                    for v in gauge_votes.votes
                ],
            }
            filename = args.output or generate_timestamped_filename(
                "gauge_votes"
            )
            save_json_output(output, filename)
            return

        console.print(
            f"[bold]Votes for gauge {format_address(gauge_address)}[/bold]"
        )
        console.print(f"Latest block: {gauge_votes.latest_block}\n")

        for vote in gauge_votes.votes:
            date = datetime.fromtimestamp(vote.time).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            user = format_address(vote.user)
            weight = f"{vote.weight/100:.2f}%"
            console.print(f"  {date} | {user} | {weight}")

    asyncio.run(run())


def cmd_user_campaign_status(args: argparse.Namespace) -> None:
    """Check proof insertion status for a user in a campaign."""

    async def run():
        chain_id = args.chain_id
        validate_chain_id(chain_id)
        platform = validate_eth_address(args.platform, "platform")
        user = validate_eth_address(args.user, "user")

        campaigns = await campaign_service.get_campaigns(
            chain_id=chain_id,
            platform_address=platform,
            campaign_id=args.campaign_id,
            check_proofs=True,
        )

        if not campaigns:
            console.print(
                f"[yellow]Campaign #{args.campaign_id} not found[/yellow]"
            )
            return

        campaign = campaigns[0]
        proof_status = await campaign_service.get_user_campaign_proof_status(
            chain_id=chain_id,
            platform_address=platform,
            campaign=campaign,
            user_address=user,
        )

        total_periods = len(proof_status["periods"])
        claimable = sum(
            1
            for p in proof_status["periods"]
            if p.get("block_updated")
            and p.get("point_data_inserted")
            and p.get("user_slope_inserted")
        )

        if args.json:
            output = {
                "campaign_id": args.campaign_id,
                "chain_id": chain_id,
                "platform": platform,
                "user": user,
                "gauge": campaign["campaign"]["gauge"],
                "total_periods": total_periods,
                "claimable_periods": claimable,
                "fully_claimable": claimable == total_periods,
                "periods": proof_status["periods"],
            }
            filename = args.output or generate_timestamped_filename(
                "user_campaign_status"
            )
            save_json_output(output, filename)
            return

        console.print(f"[bold]Campaign #{args.campaign_id} Status[/bold]")
        console.print(
            f"Gauge: {format_address(campaign['campaign']['gauge'])}"
        )
        console.print(f"User: {format_address(user)}")
        console.print(f"Claimable: {claimable}/{total_periods} periods")

        if claimable == total_periods:
            console.print("[green]✓ All proofs inserted - can claim![/green]")
        elif claimable > 0:
            console.print(
                f"[yellow]⚠ Partial proofs ({claimable}/{total_periods})[/yellow]"
            )
        else:
            console.print("[red]✗ No proofs available yet[/red]")

    asyncio.run(run())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="votemarket",
        description="Unified CLI for VoteMarket Toolkit",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # block-info
    p_block = sub.add_parser("block-info", help="Get block info")
    p_block.add_argument("--block-number", type=int, required=True)
    p_block.add_argument("--chain-id", type=int, default=1)
    p_block.add_argument("--output", type=str, help="Output filename")
    p_block.set_defaults(func=cmd_block_info)

    # proofs-user
    p_pu = sub.add_parser("proofs-user", help="Generate user proof")
    p_pu.add_argument("--protocol", type=str, required=True)
    p_pu.add_argument("--gauge-address", type=str, required=True)
    p_pu.add_argument("--user-address", type=str, required=True)
    p_pu.add_argument("--block-number", type=int, required=True)
    p_pu.add_argument("--chain-id", type=int, default=1)
    p_pu.add_argument("--output", type=str, help="Output filename")
    p_pu.set_defaults(func=cmd_proofs_user)

    # proofs-gauge
    p_pg = sub.add_parser("proofs-gauge", help="Generate gauge proof")
    p_pg.add_argument("--protocol", type=str, required=True)
    p_pg.add_argument("--gauge-address", type=str, required=True)
    p_pg.add_argument("--current-epoch", type=int, required=True)
    p_pg.add_argument("--block-number", type=int, required=True)
    p_pg.add_argument("--chain-id", type=int, default=1)
    p_pg.add_argument("--output", type=str, help="Output filename")
    p_pg.set_defaults(func=cmd_proofs_gauge)

    # campaigns-active
    p_ca = sub.add_parser(
        "campaigns-active",
        help="List active campaigns for a platform or protocol",
    )
    p_ca.add_argument(
        "--platform", type=str, help="Platform address (optional)"
    )
    p_ca.add_argument("--protocol", type=str, help="Protocol name (optional)")
    p_ca.add_argument("--chain-id", type=int, help="Chain ID (required)")
    p_ca.add_argument("--campaign-id", type=int, help="Specific campaign ID")
    p_ca.add_argument(
        "--check-proofs",
        action="store_true",
        help="Check oracle proof status for early periods",
    )
    p_ca.add_argument("--json", action="store_true", help="Output JSON")
    p_ca.add_argument("--output", type=str, help="Output filename")
    p_ca.set_defaults(func=cmd_campaigns_active)

    # users-eligibility
    p_ue = sub.add_parser(
        "users-eligibility",
        help="Check user eligibility across campaigns",
    )
    p_ue.add_argument("--user", type=str, required=True)
    p_ue.add_argument("--protocol", type=str, required=True)
    p_ue.add_argument("--gauge", type=str, help="Filter by gauge")
    p_ue.add_argument("--chain-id", type=int, help="Filter by chain")
    p_ue.add_argument(
        "--status",
        type=str,
        choices=["active", "closed", "all"],
        default="all",
    )
    p_ue.add_argument("--json", action="store_true", help="Output JSON")
    p_ue.add_argument("--output", type=str, help="Output filename")
    p_ue.set_defaults(func=cmd_users_eligibility)

    # index-votes
    p_iv = sub.add_parser(
        "index-votes",
        help="Index and display votes for a gauge",
    )
    p_iv.add_argument("--protocol", type=str, required=True)
    p_iv.add_argument("--gauge-address", type=str, required=True)
    p_iv.add_argument("--chain-id", type=int, default=1)
    p_iv.add_argument("--json", action="store_true", help="Output JSON")
    p_iv.add_argument("--output", type=str, help="Output filename")
    p_iv.set_defaults(func=cmd_index_votes)

    # user-campaign-status
    p_ucs = sub.add_parser(
        "user-campaign-status",
        help="Check proof insertion status for a user in a campaign",
    )
    p_ucs.add_argument("--chain-id", type=int, required=True)
    p_ucs.add_argument("--platform", type=str, required=True)
    p_ucs.add_argument("--campaign-id", type=int, required=True)
    p_ucs.add_argument("--user", type=str, required=True)
    p_ucs.add_argument("--json", action="store_true", help="Output JSON")
    p_ucs.add_argument("--output", type=str, help="Output filename")
    p_ucs.set_defaults(func=cmd_user_campaign_status)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as e:
        # Basic error print; avoid heavy formatting for simplicity
        console.print(f"[red]Error:[/red] {str(e)}")
        raise


if __name__ == "__main__":
    main()
