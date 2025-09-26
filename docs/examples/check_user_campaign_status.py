"""
Example: Check User Campaign Proof Status

This example demonstrates how to check if a user has all necessary proofs
inserted on the oracle for a specific VoteMarket campaign.

The script will:
1. Connect to the specified chain
2. Fetch the campaign details
3. Check proof insertion status for each period
4. Display detailed results showing what proofs are missing
"""

import asyncio
from votemarket_toolkit.campaigns.service import campaign_service

async def main():
    # Example configuration - replace with your values
    CHAIN_ID = 1  # Ethereum mainnet
    PLATFORM_ADDRESS = "0xD48dc326d834f4cBBCcDb0029Dd0E19e65bd5d36"  # Curve platform
    CAMPAIGN_ID = 123  # Example campaign ID
    USER_ADDRESS = "0x52f541764e6e90eebc5c21ff570de0e2d63766b6"  # Example user
    
    print(f"Checking proof status for user {USER_ADDRESS}")
    print(f"Campaign #{CAMPAIGN_ID} on chain {CHAIN_ID}")
    print("-" * 50)
    
    try:
        # First fetch the campaign
        campaigns = await campaign_service.get_campaigns(
            chain_id=CHAIN_ID,
            platform_address=PLATFORM_ADDRESS,
            campaign_id=CAMPAIGN_ID,
            check_proofs=False  # We'll check user-specific proofs separately
        )
        
        if not campaigns:
            print("Campaign not found!")
            return
            
        campaign = campaigns[0]
        print(f"Campaign gauge: {campaign['campaign']['gauge']}")
        print(f"Total periods: {campaign['campaign']['number_of_periods']}")
        print()
        
        # Now check user-specific proof status
        proof_status = await campaign_service.get_user_campaign_proof_status(
            chain_id=CHAIN_ID,
            platform_address=PLATFORM_ADDRESS,
            campaign=campaign,
            user_address=USER_ADDRESS
        )
        
        # Display results
        print(f"Oracle address: {proof_status['oracle_address']}")
        print(f"Checking {len(proof_status['periods'])} periods...")
        print()
        
        claimable_count = 0
        missing_proofs = []
        
        for idx, period in enumerate(proof_status['periods']):
            print(f"Period #{idx + 1} (Timestamp: {period['timestamp']})")
            print(f"  - Block header: {'✓' if period['block_updated'] else '✗'}")
            print(f"  - Point data: {'✓' if period['point_data_inserted'] else '✗'}")
            print(f"  - User slope: {'✓' if period['user_slope_inserted'] else '✗'}")
            
            if period['user_slope_data']:
                slope = period['user_slope_data']['slope']
                print(f"  - Slope value: {slope:,.0f}")
            
            if period['is_claimable']:
                print("  ✓ CLAIMABLE")
                claimable_count += 1
            else:
                print("  ✗ NOT CLAIMABLE")
                missing = []
                if not period['block_updated']:
                    missing.append("block")
                if not period['point_data_inserted']:
                    missing.append("point")
                if not period['user_slope_inserted']:
                    missing.append("slope")
                missing_proofs.append((idx + 1, missing))
            print()
        
        # Summary
        print("=" * 50)
        print("SUMMARY")
        print(f"Total periods: {len(proof_status['periods'])}")
        print(f"Claimable periods: {claimable_count}")
        print(f"Missing proofs: {len(proof_status['periods']) - claimable_count}")
        
        if claimable_count == len(proof_status['periods']):
            print("✓ All proofs are inserted - user can claim full rewards!")
        elif claimable_count > 0:
            print(f"⚠ Partial proofs available - user can claim {claimable_count} periods")
        else:
            print("✗ No proofs available - user cannot claim yet")
            
        if missing_proofs:
            print("\nMissing proof details:")
            for period_num, missing_types in missing_proofs:
                print(f"  Period #{period_num}: Missing {', '.join(missing_types)}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
