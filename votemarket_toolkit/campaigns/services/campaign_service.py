"""
CampaignService - Core service for VoteMarket campaign interactions

This service handles:
1. Fetching campaign data from on-chain contracts
2. Calculating campaign lifecycle status (active/closable/closed)
3. Checking proof insertion status for rewards claiming
4. Parallel batch fetching for performance optimization

Campaign Lifecycle Phases:
- Active: Campaign is running or has remaining periods
- Claim Period (0-6 months after end): Users can claim rewards
- Manager Close (6-7 months): Only manager can close, funds return to manager
- Public Close (7+ months): Anyone can close, funds go to fee collector

Technical Implementation:
- Uses bytecode deployment for efficient batch data fetching
- Implements adaptive parallelism based on campaign count
- Supports proof status checking via oracle contracts
"""

import asyncio
import time
from typing import Dict, List, Optional

from eth_utils import to_checksum_address

from votemarket_toolkit.campaigns.types import (
    CampaignStatus,
    CampaignStatusInfo,
    Platform,
)
from votemarket_toolkit.contracts.reader import ContractReader
from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.services.resource_manager import (
    resource_manager,
)
from votemarket_toolkit.shared.services.web3_service import Web3Service


class CampaignService:
    """
    Service for fetching and managing VoteMarket campaign data.

    This service provides high-level methods for interacting with VoteMarket
    platform contracts to retrieve campaign information, check status, and
    verify proof insertions.

    Attributes:
        contract_reader: Handles contract interaction and data decoding
        web3_services: Cache of Web3Service instances per chain
    """

    def __init__(self):
        """Initialize the campaign service with contract reader and service cache."""
        self.contract_reader = ContractReader()
        self.web3_services: Dict[int, Web3Service] = {}

    def get_web3_service(self, chain_id: int) -> Web3Service:
        """
        Get or create a Web3Service instance for a specific chain.

        Uses a cache to avoid recreating services for the same chain.

        Args:
            chain_id: The blockchain network ID (1 for Ethereum, 42161 for Arbitrum)

        Returns:
            Web3Service: Configured web3 service instance for the chain
        """
        if chain_id not in self.web3_services:
            self.web3_services[chain_id] = Web3Service.get_instance(chain_id)
        return self.web3_services[chain_id]

    def calculate_campaign_status(
        self, campaign: Dict, current_timestamp: Optional[int] = None
    ) -> CampaignStatusInfo:
        """
        Calculate detailed campaign status based on VoteMarket V2 lifecycle rules.

        VoteMarket V2 campaigns have specific time-based closing windows:
        1. First 6 months after end: Users can claim rewards (NOT_CLOSABLE)
        2. Months 6-7 after end: Manager can close, funds return to manager (CLOSABLE_BY_MANAGER)
        3. After 7 months: Anyone can close, funds go to fee collector (CLOSABLE_BY_EVERYONE)

        Args:
            campaign: Campaign data dictionary containing:
                - is_closed: Boolean indicating if campaign is already closed
                - campaign: Dict with campaign details including end_timestamp
                - remaining_periods: Number of periods still to be distributed
            current_timestamp: Current timestamp in seconds (defaults to now)

        Returns:
            CampaignStatusInfo: Dictionary containing:
                - status: CampaignStatus enum value
                - is_closed: Boolean indicating if closed
                - can_close: Boolean indicating if closable now
                - who_can_close: "no_one", "manager_only", or "everyone"
                - days_until_public_close: Days until anyone can close (or None)
                - reason: Human-readable explanation of status

        Example:
            >>> status = service.calculate_campaign_status(campaign_data)
            >>> if status["can_close"]:
            >>>     print(f"Campaign can be closed by: {status['who_can_close']}")
        """
        if current_timestamp is None:
            current_timestamp = int(time.time())

        # If already closed
        if campaign.get("is_closed", False):
            return {
                "status": CampaignStatus.CLOSED,
                "is_closed": True,
                "can_close": False,
                "who_can_close": "no_one",
                "days_until_public_close": None,
                "reason": "Campaign is already closed",
            }

        # Get campaign details
        c = campaign.get("campaign", {})
        end_timestamp = c.get("end_timestamp", 0)
        remaining_periods = campaign.get("remaining_periods", 0)

        # Calculate time since end
        seconds_since_end = current_timestamp - end_timestamp
        days_since_end = seconds_since_end / 86400  # Convert to days

        # VoteMarket V2 thresholds
        CLAIM_DEADLINE_DAYS = 180  # 6 months = ~180 days
        MANAGER_CLOSE_DAYS = 210  # 7 months = ~210 days

        # If campaign hasn't ended yet or has remaining periods
        if current_timestamp < end_timestamp or remaining_periods > 0:
            return {
                "status": CampaignStatus.ACTIVE,
                "is_closed": False,
                "can_close": False,
                "who_can_close": "no_one",
                "days_until_public_close": None,
                "reason": f"Campaign is active with {remaining_periods} periods remaining",
            }

        # Campaign has ended, check which phase we're in
        if days_since_end < CLAIM_DEADLINE_DAYS:
            # Still in claim period (first 6 months)
            days_until_manager_close = CLAIM_DEADLINE_DAYS - days_since_end
            return {
                "status": CampaignStatus.NOT_CLOSABLE,
                "is_closed": False,
                "can_close": False,
                "who_can_close": "no_one",
                "days_until_public_close": None,
                "reason": f"In claim period - {int(days_until_manager_close)} days until manager can close",
            }

        elif days_since_end < MANAGER_CLOSE_DAYS:
            # In manager-only close window (months 6-7)
            days_since_claim_deadline = days_since_end - CLAIM_DEADLINE_DAYS
            days_until_public = MANAGER_CLOSE_DAYS - days_since_end
            return {
                "status": CampaignStatus.CLOSABLE_BY_MANAGER,
                "is_closed": False,
                "can_close": True,
                "who_can_close": "manager_only",
                "days_until_public_close": int(days_until_public),
                "reason": f"Manager can close ({int(days_since_claim_deadline)} days past claim deadline, public in {int(days_until_public)} days)",
            }

        else:
            # After 7 months - anyone can close
            days_since_public_close = days_since_end - MANAGER_CLOSE_DAYS
            return {
                "status": CampaignStatus.CLOSABLE_BY_EVERYONE,
                "is_closed": False,
                "can_close": True,
                "who_can_close": "everyone",
                "days_until_public_close": 0,
                "reason": f"Anyone can close ({int(days_since_public_close)} days past public close date) - funds go to fee collector",
            }

    def get_all_platforms(self, protocol: str) -> List[Platform]:
        """
        Get all VoteMarket platform addresses for a specific protocol.

        Args:
            protocol: Protocol name ("curve", "balancer", "frax", "fxn", "pendle")

        Returns:
            List[Platform]: List of platform configurations including addresses and chain IDs

        Example:
            >>> platforms = service.get_all_platforms("curve")
            >>> for platform in platforms:
            >>>     print(f"Chain {platform.chain_id}: {platform.address}")
        """
        return registry.get_all_platforms(protocol)

    async def get_campaigns(
        self,
        chain_id: int,
        platform_address: str,
        campaign_id: Optional[int] = None,
        check_proofs: bool = False,
        parallel_requests: int = 5,
    ) -> List[Dict]:
        """
        Get campaigns with periods and optional proof checking.

        This method uses an optimized batch fetching strategy:
        1. Deploys bytecode to fetch multiple campaigns in a single call
        2. Uses adaptive parallelism based on total campaign count
        3. Optionally checks proof insertion status via oracle

        Batch Size Strategy:
        - >200 campaigns: batch_size=1, parallelism=2 (avoid timeouts)
        - >100 campaigns: batch_size=1, parallelism=3
        - >50 campaigns: batch_size=2, parallelism=4
        - <=50 campaigns: batch_size=2, parallelism=5

        Args:
            chain_id: Chain ID to query (1 for Ethereum, 42161 for Arbitrum)
            platform_address: VoteMarket platform contract address
            campaign_id: Specific campaign ID to fetch (None fetches all)
            check_proofs: Whether to check proof insertion status (adds oracle queries)
            parallel_requests: Maximum number of concurrent requests (default 5)

        Returns:
            List[Dict]: List of campaign dictionaries, each containing:
                - campaign: Core campaign data (gauge, manager, rewards, etc.)
                - periods: List of period data with timestamps and amounts
                - remaining_periods: Number of undistributed periods
                - is_closed: Whether campaign has been closed
                - status_info: Calculated lifecycle status
                - point_data_inserted (if check_proofs=True): Proof status

        Raises:
            Exception: If web3 service unavailable or contract calls fail

        Example:
            >>> campaigns = await service.get_campaigns(
            ...     chain_id=1,
            ...     platform_address="0x...",
            ...     check_proofs=True
            ... )
            >>> for campaign in campaigns:
            >>>     print(f"Campaign {campaign['campaign']['id']}: {campaign['status_info']['status']}")
        """
        try:
            web3_service = self.get_web3_service(chain_id)
            if not web3_service:
                print(f"Web3 service not available for chain {chain_id}")
                return []

            platform_contract = web3_service.get_contract(
                to_checksum_address(platform_address.lower()),
                "vm_platform",
            )

            # If specific campaign ID requested
            if campaign_id is not None:
                # Just fetch the single campaign
                total_campaigns = 1
            else:
                # Get total campaign count
                total_campaigns = (
                    platform_contract.functions.campaignCount().call()
                )
                if total_campaigns == 0:
                    return []

            # Load bytecode once for batch fetching
            # This bytecode deploys a temporary contract that reads multiple campaigns
            # in a single call, significantly reducing RPC overhead
            bytecode_data = resource_manager.load_bytecode(
                "BatchCampaignsWithPeriods"
            )

            # Track errors for reporting
            errors_count = 0

            # Helper function for fetching a single batch of campaigns
            async def fetch_batch(start_idx: int, limit: int) -> List[Dict]:
                """
                Fetch a batch of campaigns from the blockchain.

                Args:
                    start_idx: Starting campaign ID
                    limit: Number of campaigns to fetch

                Returns:
                    List of decoded campaign data or empty list on error
                """
                nonlocal errors_count
                try:
                    # Build constructor transaction with bytecode and parameters
                    tx = self.contract_reader.build_get_campaigns_with_periods_constructor_tx(
                        bytecode_data,
                        [platform_address, start_idx, limit],
                    )
                    # Execute call asynchronously to avoid blocking
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, web3_service.w3.eth.call, tx
                    )
                    # Decode the raw result into structured campaign data
                    return (
                        self.contract_reader.decode_campaign_data_with_periods(
                            result
                        )
                    )
                except Exception:
                    errors_count += 1
                    return []

            # Create batch tasks
            tasks = []

            if campaign_id is not None:
                # Single campaign fetch
                tasks.append(fetch_batch(campaign_id, 1))
                effective_parallel = 1
            else:
                # Determine optimal batch size and parallelism based on campaign count
                # This adaptive strategy prevents RPC timeouts while maximizing throughput
                if total_campaigns > 200:
                    # Very large datasets: fetch one at a time with low parallelism
                    batch_size = 1
                    effective_parallel = 2
                elif total_campaigns > 100:
                    # Large datasets: still one at a time but slightly more parallel
                    batch_size = 1
                    effective_parallel = 3
                elif total_campaigns > 50:
                    # Medium datasets: fetch 2 at a time with moderate parallelism
                    batch_size = 2
                    effective_parallel = 4
                else:
                    # Small datasets: can be more aggressive
                    batch_size = 2
                    effective_parallel = min(parallel_requests, 5)

                # Create all batch tasks
                for start_idx in range(0, total_campaigns, batch_size):
                    limit = min(batch_size, total_campaigns - start_idx)
                    tasks.append(fetch_batch(start_idx, limit))

            # Execute in parallel chunks
            all_campaigns = []
            total_batches = len(tasks)

            # Show fetching status
            if campaign_id is not None:
                print(f"Fetching campaign #{campaign_id}...")
            else:
                print(
                    f"Fetching {total_campaigns} campaigns in {total_batches} batches (parallelism: {effective_parallel})..."
                )

            for i in range(0, len(tasks), effective_parallel):
                chunk = tasks[i : i + effective_parallel]
                results = await asyncio.gather(*chunk, return_exceptions=True)

                for result in results:
                    if isinstance(result, list):
                        all_campaigns.extend(result)

                # Small delay between chunks to avoid rate limiting
                if i + effective_parallel < len(tasks):
                    await asyncio.sleep(0.05)

            # Print summary
            success_count = len(all_campaigns)
            if errors_count > 0:
                print(
                    f"✓ Fetched {success_count}/{total_campaigns} campaigns ({errors_count} errors)"
                )
            else:
                print(f"✓ Successfully fetched all {success_count} campaigns")

            # Optionally check proof insertion status for reward claiming
            # This verifies if the oracle has received the necessary proofs
            # for users to be able to claim their rewards
            if check_proofs and all_campaigns:
                try:
                    # Get oracle address through lens contract
                    # Chain: platform.ORACLE() returns lens, lens.oracle() returns actual oracle
                    oracle_lens_address = (
                        platform_contract.functions.ORACLE().call()
                    )

                    oracle_lens_contract = web3_service.get_contract(
                        to_checksum_address(oracle_lens_address),
                        "lens_oracle",
                    )
                    oracle_address = (
                        oracle_lens_contract.functions.oracle().call()
                    )

                    print("Checking proof insertion status...")

                    # Load GetInsertedProofs bytecode
                    proof_bytecode = resource_manager.load_bytecode(
                        "GetInsertedProofs"
                    )

                    # Check proof insertion for each campaign
                    for campaign in all_campaigns:
                        if not campaign.get("periods"):
                            continue

                        gauge = campaign["campaign"]["gauge"]
                        # Check first 10 periods to avoid excessive calls
                        epochs = [
                            p["timestamp"] for p in campaign["periods"][:10]
                        ]

                        if not epochs:
                            continue

                        try:
                            # Build transaction to check if proofs are inserted for these epochs
                            tx = self.contract_reader.build_get_inserted_proofs_constructor_tx(
                                {"bytecode": proof_bytecode},
                                oracle_address,
                                gauge,
                                [],  # No user addresses needed for gauge-level check
                                epochs,
                            )

                            result = web3_service.w3.eth.call(tx)
                            epoch_results = (
                                self.contract_reader.decode_inserted_proofs(
                                    result
                                )
                            )

                            # Update each period with its proof insertion status
                            for period in campaign["periods"]:
                                # Find matching epoch result
                                epoch_result = next(
                                    (
                                        er
                                        for er in epoch_results
                                        if er["epoch"] == period["timestamp"]
                                    ),
                                    None,
                                )

                                if epoch_result:
                                    # Check if point data (vote weights) have been inserted
                                    point_inserted = any(
                                        pd["is_updated"]
                                        for pd in epoch_result.get(
                                            "point_data_results", []
                                        )
                                    )
                                    period["point_data_inserted"] = (
                                        point_inserted
                                    )
                                    # Check if block number has been set for this epoch
                                    period["block_updated"] = epoch_result.get(
                                        "is_block_updated", False
                                    )

                        except Exception:
                            # Skip if proof check fails for this campaign
                            pass

                    print("✓ Proof status check completed")

                except Exception as e:
                    print(f"Warning: Could not check proofs: {str(e)[:100]}")

            # Calculate lifecycle status for each campaign
            # This adds detailed status information for UI display and decision making
            for campaign in all_campaigns:
                campaign["status_info"] = self.calculate_campaign_status(
                    campaign
                )

            return all_campaigns

        except Exception as e:
            error_msg = str(e)
            print(f"Error fetching campaigns: {error_msg}")

            return []


# Create global instance
campaign_service = CampaignService()
