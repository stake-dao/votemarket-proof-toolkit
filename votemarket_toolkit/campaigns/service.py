"""
CampaignService - Core service for VoteMarket campaign interactions

This service handles:
1. Fetching campaign data from on-chain contracts
2. Calculating campaign lifecycle status (active/closable/closed)
3. Checking proof insertion status for rewards claiming
4. Parallel batch fetching for performance optimization
5. LaPoste token wrapping/unwrapping detection

Campaign Lifecycle Phases:
- Active: Campaign is running or has remaining periods
- Claim Period (0-6 months after end): Users can claim rewards
- Manager Close (6-7 months): Only manager can close, funds return to manager
- Public Close (7+ months): Anyone can close, funds go to fee collector

Technical Implementation:
- Uses bytecode deployment for efficient batch data fetching
- Implements adaptive parallelism based on campaign count
- Supports proof status checking via oracle contracts
- Handles LaPoste wrapped tokens and their native counterparts
"""

import asyncio
from typing import Dict, List, Optional

from eth_utils.address import to_checksum_address

from votemarket_toolkit.campaigns.models import Campaign, Platform
from votemarket_toolkit.contracts.reader import ContractReader
from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.services.laposte_service import laposte_service
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

    def get_all_platforms(self, protocol: str) -> List[Platform]:
        """
        Get all VoteMarket platform addresses for a specific protocol.

        Args:
            protocol: Protocol name ("curve", "balancer", "frax", "fxn", "pendle")

        Returns:
            List[Platform]: List of platform objects including addresses and chain IDs

        Example:
            >>> platforms = service.get_all_platforms("curve")
            >>> for platform in platforms:
            >>>     print(f"Chain {platform.chain_id}: {platform.address}")
        """
        dict_platforms = registry.get_all_platforms(protocol)
        return [Platform(**p) for p in dict_platforms]

    async def get_campaigns(
        self,
        chain_id: int,
        platform_address: str,
        campaign_id: Optional[int] = None,
        check_proofs: bool = False,
        parallel_requests: int = 8,
    ) -> List[Campaign]:
        """
        Get campaigns with periods and optional proof checking.

        This method uses an optimized batch fetching strategy:
        1. Deploys bytecode to fetch multiple campaigns in a single call
        2. Uses adaptive parallelism based on total campaign count
        3. Optionally checks proof insertion status via oracle

        Batch Size Strategy (optimized for reliability):
        - >400 campaigns: batch_size=5
        - >200 campaigns: batch_size=8
        - >100 campaigns: batch_size=10
        - >50 campaigns: batch_size=15
        - <=50 campaigns: batch_size=20

        Parallelism is controlled by the parallel_requests parameter (default: 8).
        Failed batches are automatically retried by splitting them in half.

        Args:
            chain_id: Chain ID to query (1 for Ethereum, 42161 for Arbitrum)
            platform_address: VoteMarket platform contract address
            campaign_id: Specific campaign ID to fetch (None fetches all)
            check_proofs: Whether to check proof insertion status (adds oracle queries)
            parallel_requests: Maximum number of concurrent requests (default 8)

        Returns:
            List[Campaign]: List of campaign objects, each containing:
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
            async def fetch_batch(
                start_idx: int, limit: int, retry_count: int = 0
            ) -> List[Dict]:
                """
                Fetch a batch of campaigns from the blockchain with retry logic.

                Args:
                    start_idx: Starting campaign ID
                    limit: Number of campaigns to fetch
                    retry_count: Current retry attempt

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
                        None,
                        web3_service.w3.eth.call,
                        tx,  # type: ignore
                    )
                    # Decode the raw result into structured campaign data
                    return self.contract_reader.decode_campaign_data(result)
                except Exception:
                    # If we have retries left and batch size > 1, try splitting the batch
                    if retry_count < 2 and limit > 1:
                        # Split batch in half and try again
                        mid_point = limit // 2
                        results1 = await fetch_batch(
                            start_idx, mid_point, retry_count + 1
                        )
                        results2 = await fetch_batch(
                            start_idx + mid_point,
                            limit - mid_point,
                            retry_count + 1,
                        )
                        return results1 + results2
                    else:
                        errors_count += 1
                        return []

            # Create batch tasks
            tasks = []

            if campaign_id is not None:
                # Single campaign fetch
                tasks.append(fetch_batch(campaign_id, 1))
                effective_parallel = 1
            else:
                # Determine optimal batch size based on campaign count
                # Conservative strategy to minimize errors while maintaining good performance
                if total_campaigns > 400:
                    # Very large datasets: smaller batches
                    batch_size = 5
                elif total_campaigns > 200:
                    # Large datasets: moderate batch size
                    batch_size = 8
                elif total_campaigns > 100:
                    # Medium-large datasets: balanced approach
                    batch_size = 10
                elif total_campaigns > 50:
                    # Medium datasets: larger batches
                    batch_size = 15
                else:
                    # Small datasets: can be more aggressive
                    batch_size = 20

                # Use the provided parallel_requests parameter
                effective_parallel = parallel_requests

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
                    await asyncio.sleep(0.15)

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

                            result = web3_service.w3.eth.call(tx)  # type: ignore
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

            # Fetch token information (both native and receipt tokens)
            await self._enrich_token_information(all_campaigns, chain_id)

            return all_campaigns

        except Exception as e:
            print(f"Error getting campaigns: {str(e)}")
            return []

    async def _enrich_token_information(
        self, campaigns: List[Campaign], chain_id: int
    ) -> None:
        """
        Enrich campaigns with token information including LaPoste wrapped tokens.

        For each campaign, this method:
        1. Gets the receipt reward token (what's stored on-chain)
        2. Checks if it's a LaPoste wrapped token
        3. If wrapped, fetches the native token information
        4. Adds both receiptRewardToken and rewardToken to campaign data

        Args:
            campaigns: List of campaigns to enrich
            chain_id: Chain ID
        """
        if not campaigns:
            return

        # Collect unique reward tokens
        unique_tokens = list(
            set(
                c["campaign"]["reward_token"]
                for c in campaigns
                if c.get("campaign", {}).get("reward_token")
            )
        )

        if not unique_tokens:
            return

        try:
            # Get native tokens for all wrapped tokens
            native_tokens = await laposte_service.get_native_tokens(
                chain_id, unique_tokens
            )

            # Create mapping of wrapped to native
            token_mapping = dict(zip(unique_tokens, native_tokens))

            # Fetch token information for receipt tokens (on current chain)
            token_info_cache = {}

            for token in unique_tokens:
                if token:
                    info = await laposte_service.get_token_info(
                        chain_id,
                        token,
                        is_native=False,
                        original_chain_id=chain_id,
                    )
                    token_info_cache[token.lower()] = info

            # Fetch native token information (might be on mainnet)
            for i, native_token in enumerate(native_tokens):
                if (
                    native_token
                    and native_token.lower() != unique_tokens[i].lower()
                ):
                    # It's a different token (wrapped), fetch from mainnet
                    info = await laposte_service.get_token_info(
                        chain_id,
                        native_token,
                        is_native=True,
                        original_chain_id=chain_id,
                    )
                    token_info_cache[native_token.lower()] = info

            # Enrich each campaign
            for campaign in campaigns:
                reward_token = campaign["campaign"].get("reward_token")
                if not reward_token:
                    continue

                reward_token_lower = reward_token.lower()
                native_token = token_mapping.get(reward_token, reward_token)
                native_token_lower = (
                    native_token.lower()
                    if native_token
                    else reward_token_lower
                )

                # Get receipt token info (the wrapped/LaPoste token on-chain)
                receipt_info = token_info_cache.get(
                    reward_token_lower,
                    {
                        "name": "Unknown",
                        "symbol": "???",
                        "address": reward_token,
                        "decimals": 18,
                        "chainId": chain_id,
                        "price": 0.0,
                    },
                )

                # Get native token info
                if native_token_lower != reward_token_lower:
                    # It's wrapped, get the native token info
                    native_info = token_info_cache.get(
                        native_token_lower, receipt_info
                    )
                else:
                    # Not wrapped, both are the same
                    native_info = receipt_info

                campaign["receipt_reward_token"] = receipt_info
                campaign["reward_token"] = native_info

        except Exception as e:
            print(
                f"Warning: Could not enrich token information: {str(e)[:100]}"
            )

    async def get_user_campaign_proof_status(
        self,
        chain_id: int,
        platform_address: str,
        campaign: Dict,
        user_address: str,
    ) -> Dict:
        """
        Get detailed proof insertion status for a specific user in a campaign.

        This method checks if a user has all necessary proofs inserted on the oracle
        to be able to claim rewards for each period of the campaign.

        For each period, it verifies:
        1. Block header is set (required for merkle proof verification)
        2. Point data is inserted (gauge total voting power at that epoch)
        3. User slope data is inserted (user's specific vote for the gauge)

        Args:
            chain_id: Chain ID (1 for Ethereum, 42161 for Arbitrum)
            platform_address: VoteMarket platform contract address
            campaign: Campaign dictionary with periods and gauge info
            user_address: User address to check proofs for

        Returns:
            Dictionary containing:
                - oracle_address: Address of the oracle contract
                - gauge: Gauge address for the campaign
                - user: User address checked
                - periods: List of period status dictionaries, each with:
                    - timestamp: Period epoch timestamp
                    - block_updated: Whether block header is set
                    - point_data_inserted: Whether gauge point data exists
                    - user_slope_inserted: Whether user vote data exists
                    - user_slope_data: Actual slope values (slope, end, lastVote, lastUpdate)
                    - is_claimable: Overall status if user can claim for this period

        Example:
            >>> status = await service.get_user_campaign_proof_status(
            ...     chain_id=1,
            ...     platform_address="0x...",
            ...     campaign=campaign_data,
            ...     user_address="0x..."
            ... )
            >>> for period in status["periods"]:
            >>>     if period["is_claimable"]:
            >>>         print(f"User can claim for period {period['timestamp']}")
        """
        try:
            web3_service = self.get_web3_service(chain_id)
            if not web3_service:
                raise Exception(
                    f"Web3 service not available for chain {chain_id}"
                )

            # Get oracle address from platform
            platform_contract = web3_service.get_contract(
                to_checksum_address(platform_address.lower()),
                "vm_platform",
            )

            # Get oracle through lens
            oracle_lens_address = platform_contract.functions.ORACLE().call()
            oracle_lens_contract = web3_service.get_contract(
                to_checksum_address(oracle_lens_address),
                "lens_oracle",
            )
            oracle_address = oracle_lens_contract.functions.oracle().call()

            # Get gauge from campaign
            gauge = campaign["campaign"]["gauge"]

            # Prepare epochs from campaign periods
            if not campaign.get("periods"):
                return {
                    "oracle_address": oracle_address,
                    "gauge": gauge,
                    "user": user_address,
                    "periods": [],
                }

            epochs = [p["timestamp"] for p in campaign["periods"]]

            # Load GetInsertedProofs bytecode
            proof_bytecode = resource_manager.load_bytecode(
                "GetInsertedProofs"
            )

            # Build and execute the proof check transaction
            tx = self.contract_reader.build_get_inserted_proofs_constructor_tx(
                {"bytecode": proof_bytecode},
                oracle_address,
                gauge,
                [user_address],  # Check for this specific user
                epochs,
            )

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                web3_service.w3.eth.call,
                tx,  # type: ignore
            )

            # Decode the results
            epoch_results = self.contract_reader.decode_inserted_proofs(result)

            # Get detailed slope data for each period
            # We need to fetch the actual slope values to show the user
            oracle_contract = web3_service.get_contract(
                to_checksum_address(oracle_address),
                "oracle",
            )

            # Build comprehensive status for each period
            period_status = []
            for period in campaign["periods"]:
                epoch = period["timestamp"]

                # Find matching epoch result from GetInsertedProofs
                epoch_result = next(
                    (er for er in epoch_results if er["epoch"] == epoch), None
                )

                status_entry = {
                    "timestamp": epoch,
                    "block_updated": False,
                    "point_data_inserted": False,
                    "user_slope_inserted": False,
                    "user_slope_data": None,
                    "is_claimable": False,
                }

                if epoch_result:
                    # Block header status
                    status_entry["block_updated"] = epoch_result.get(
                        "is_block_updated", False
                    )

                    # Point data status (gauge total votes)
                    point_results = epoch_result.get("point_data_results", [])
                    if point_results:
                        status_entry["point_data_inserted"] = point_results[
                            0
                        ].get("is_updated", False)

                    # User slope data status
                    slope_results = epoch_result.get(
                        "voted_slope_data_results", []
                    )
                    if slope_results:
                        # Find the user's specific result
                        user_result = next(
                            (
                                sr
                                for sr in slope_results
                                if sr["account"].lower()
                                == user_address.lower()
                            ),
                            None,
                        )
                        if user_result:
                            status_entry["user_slope_inserted"] = (
                                user_result.get("is_updated", False)
                            )

                            # Fetch actual slope values if data exists
                            if status_entry["user_slope_inserted"]:
                                try:
                                    slope_data = oracle_contract.functions.votedSlopeByEpoch(
                                        to_checksum_address(user_address),
                                        to_checksum_address(gauge),
                                        epoch,
                                    ).call()

                                    status_entry["user_slope_data"] = {
                                        "slope": slope_data[0],
                                        "end": slope_data[1],
                                        "last_vote": slope_data[2],
                                        "last_update": slope_data[3],
                                    }
                                except Exception:
                                    # If we can't fetch the actual data, just skip
                                    pass

                # Determine if this period is claimable
                status_entry["is_claimable"] = (
                    status_entry["block_updated"]
                    and status_entry["point_data_inserted"]
                    and status_entry["user_slope_inserted"]
                )

                period_status.append(status_entry)

            return {
                "oracle_address": oracle_address,
                "gauge": gauge,
                "user": user_address,
                "periods": period_status,
            }

        except Exception as e:
            raise Exception(f"Error checking user proof status: {str(e)}")


# Create global instance
campaign_service = CampaignService()
