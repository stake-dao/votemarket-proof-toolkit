"""Campaign Service - Interaction with platforms to fetch campaigns and their periods + proofs"""

import asyncio
from typing import Dict, List

from eth_utils import to_checksum_address
from votemarket_toolkit.campaigns.types import (
    Platform,
    CampaignStatus,
    CampaignStatusInfo,
)
import time
from votemarket_toolkit.contracts.reader import ContractReader
from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.services.resource_manager import (
    resource_manager,
)
from votemarket_toolkit.shared.services.web3_service import Web3Service


class CampaignService:
    """Service for fetching campaign data"""

    def __init__(self):
        self.contract_reader = ContractReader()
        self.web3_services = {}

    def get_web3_service(self, chain_id: int) -> Web3Service:
        """Get or create a web3 service for a specific chain"""
        if chain_id not in self.web3_services:
            self.web3_services[chain_id] = Web3Service.get_instance(chain_id)
        return self.web3_services[chain_id]

    def calculate_campaign_status(
        self, campaign: Dict, current_timestamp: int = None
    ) -> CampaignStatusInfo:
        """
        Calculate detailed campaign status.

        VoteMarket V2 campaigns have specific closing windows:
        1. First 6 months after end: Users can claim rewards
        2. Months 6-7 after end: Manager can close (funds return to manager)
        3. After 7 months: Anyone can close (funds go to fee collector)

        Args:
            campaign: Campaign data dictionary
            current_timestamp: Current timestamp (defaults to now)

        Returns:
            CampaignStatusInfo with detailed status
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
        months_since_end = days_since_end / 30  # Approximate months

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
        """Get all platforms for a protocol"""
        return registry.get_all_platforms(protocol)

    async def get_campaigns(
        self,
        chain_id: int,
        platform_address: str,
        campaign_id: int = None,
        check_proofs: bool = False,
        parallel_requests: int = 5,
    ) -> List[Dict]:
        """
        Get campaigns with periods and optional proof checking.

        Args:
            chain_id: Chain ID to query
            platform_address: Votemarket platform address
            campaign_id: Specific campaign ID to fetch (None for all)
            check_proofs: Whether to check proof insertion status
            parallel_requests: Number of concurrent requests (default 5)

        Returns:
            List of campaign dictionaries with all periods included
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

            # Load bytecode once
            bytecode_data = resource_manager.load_bytecode(
                "BatchCampaignsWithPeriods"
            )

            # Track errors
            errors_count = 0

            # Helper function for fetching a single batch
            async def fetch_batch(start_idx: int, limit: int) -> List[Dict]:
                nonlocal errors_count
                try:
                    tx = self.contract_reader.build_get_campaigns_with_periods_constructor_tx(
                        bytecode_data,
                        [platform_address, start_idx, limit],
                    )
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, web3_service.w3.eth.call, tx
                    )
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
                # Determine optimal batch size and parallelism
                if total_campaigns > 200:
                    batch_size = 1
                    effective_parallel = 2
                elif total_campaigns > 100:
                    batch_size = 1
                    effective_parallel = 3
                elif total_campaigns > 50:
                    batch_size = 2
                    effective_parallel = 4
                else:
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

            # Optionally check proof insertion status
            if check_proofs and all_campaigns:
                try:
                    # Get oracle address: platform.ORACLE() -> lens.oracle()
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

                    print(f"Checking proof insertion status...")

                    # Load GetInsertedProofs bytecode
                    proof_bytecode = resource_manager.load_bytecode(
                        "GetInsertedProofs"
                    )

                    # Check proofs for each campaign
                    for campaign in all_campaigns:
                        if not campaign.get("periods"):
                            continue

                        gauge = campaign["campaign"]["gauge"]
                        epochs = [
                            p["timestamp"] for p in campaign["periods"][:10]
                        ]  # Limit to 10

                        if not epochs:
                            continue

                        try:
                            # Check proofs for this gauge
                            tx = self.contract_reader.build_get_inserted_proofs_constructor_tx(
                                {"bytecode": proof_bytecode},
                                oracle_address,
                                gauge,
                                [],  # No user addresses needed
                                epochs,
                            )

                            result = web3_service.w3.eth.call(tx)
                            epoch_results = (
                                self.contract_reader.decode_inserted_proofs(
                                    result
                                )
                            )

                            # Update periods with proof status
                            for period in campaign["periods"]:
                                epoch_result = next(
                                    (
                                        er
                                        for er in epoch_results
                                        if er["epoch"] == period["timestamp"]
                                    ),
                                    None,
                                )

                                if epoch_result:
                                    point_inserted = any(
                                        pd["is_updated"]
                                        for pd in epoch_result.get(
                                            "point_data_results", []
                                        )
                                    )
                                    period["point_data_inserted"] = (
                                        point_inserted
                                    )
                                    period["block_updated"] = epoch_result.get(
                                        "is_block_updated", False
                                    )

                        except:
                            # Skip if proof check fails for this campaign
                            pass

                    print("✓ Proof status check completed")

                except Exception as e:
                    print(f"Warning: Could not check proofs: {str(e)[:100]}")

            # Calculate status for each campaign
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
