#!/usr/bin/env python3
"""Check user eligibility across all campaigns for a protocol."""

import asyncio
import sys
from datetime import datetime, timezone

from eth_utils import to_checksum_address

from votemarket_toolkit.proofs.user_eligibility_service import UserEligibilityService


# Chain names mapping
CHAIN_NAMES = {
    1: "Ethereum",
    10: "Optimism", 
    137: "Polygon",
    8453: "Base",
    42161: "Arbitrum"
}


async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Check user eligibility across all campaigns"
    )
    parser.add_argument(
        "--user",
        type=str,
        required=True,
        help="User address to check"
    )
    parser.add_argument(
        "--protocol",
        type=str,
        required=True,
        help="Protocol (curve, balancer, fxn, pendle)"
    )
    parser.add_argument(
        "--gauge",
        type=str,
        help="Specific gauge to check (optional, for closed campaigns)"
    )
    parser.add_argument(
        "--chain-id",
        type=int,
        help="Chain ID (default: check all chains)"
    )
    parser.add_argument(
        "--status",
        type=str,
        choices=["active", "closed", "all"],
        default="all",
        help="Filter by campaign status (default: all)"
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    protocol = args.protocol.lower()
    user = to_checksum_address(args.user)
    
    print(f"\n\033[1m\033[96mChecking eligibility for user: {user}\033[0m")
    print(f"\033[1m\033[96mProtocol: {protocol.upper()}\033[0m\n")
    
    # Warning if no gauge specified
    if not args.gauge:
        print("\033[93m⚠️  WARNING: Checking all campaigns can take several minutes!\033[0m")
        print("\033[93m   This will check hundreds of campaigns across all gauges.\033[0m")
        print("\033[93m   For faster results, use --gauge to check a specific gauge.\033[0m\n")
        print("Tips for faster results:")
        print("  • Use --gauge <address> to check a specific gauge")
        print("  • Use --status active to only check active campaigns")
        print("  • Check your voting history on the governance platform first\n")
    
    # Use the service
    service = UserEligibilityService()
    
    try:
        results = await service.check_user_eligibility(
            user=user,
            protocol=protocol,
            chain_id=args.chain_id,
            gauge_address=args.gauge,
            status_filter=args.status
        )
        
        # Display summary
        summary = results['summary']
        if summary['total_campaigns_checked'] == 0:
            print(f"\033[93mNo campaigns found for protocol {protocol}\033[0m")
            return
            
        print(f"\033[92m=== Summary ===\033[0m")
        print(f"Total campaigns checked: {summary['total_campaigns_checked']}")
        print(f"Campaigns with your votes: {summary['campaigns_with_eligibility']}")
        print(f"Claimable periods: {summary['total_claimable_periods']}")
        
        # Display results by chain
        for chain_id, chain_data in results['chains'].items():
            chain_name = CHAIN_NAMES.get(chain_id, f"Chain {chain_id}")
            print(f"\n\033[93m{chain_name} Results:\033[0m")
            
            for campaign in chain_data['campaigns']:
                status = "ACTIVE" if not campaign['is_closed'] else "CLOSED"
                print(f"\n{'='*80}")
                print(f"Campaign #{campaign['id']} ({status}) - Gauge: {campaign['gauge'][:10]}...")
                print(f"Manager: {campaign['manager'][:10]}...")
                print(f"Reward Token: {campaign['reward_token'][:10]}...")
                print(f"{'='*80}")
                
                # Print table header
                print(f"{'Period':<10} {'Epoch Date':<22} {'Status':<10} {'Has Proof':<10} {'Claimable':<10} {'Notes':<30}")
                print("-" * 90)
                
                for period in campaign['periods']:
                    epoch_date = datetime.fromtimestamp(period['epoch'], tz=timezone.utc)
                    has_proof = "✓" if period['has_proof'] else "✗"
                    claimable = "✓" if period['claimable'] else "✗"
                    print(f"#{period['period']:<9} {epoch_date.strftime('%Y-%m-%d %H:%M UTC'):<22} {period['status']:<10} {has_proof:<10} {claimable:<10} {period['reason']:<30}")
        
        if summary['campaigns_with_eligibility'] == 0:
            print("\n\033[93mNo campaigns found where user has votes or is eligible to claim\033[0m")
        
        print("\n\033[92mCheck complete!\033[0m")
        
        if summary['total_claimable_periods'] > 0:
            print("\nTo generate proofs for claimable periods:")
            print(f"\033[96m  make user-proof USER={user} GAUGE=<gauge_address> PROTOCOL={protocol} BLOCK=<block_number>\033[0m")
            print("\nOr download pre-generated proofs from:")
            print(f"\033[96m  https://github.com/stake-dao/api/tree/main/api/votemarket\033[0m")
            
    except Exception as e:
        print(f"\n\033[91mError: {e}\033[0m")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\033[93mInterrupted by user\033[0m")
        sys.exit(0)
    except Exception as e:
        print(f"\n\033[91mError: {e}\033[0m")
        sys.exit(1)