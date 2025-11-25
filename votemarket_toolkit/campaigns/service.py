"""
CampaignService - Core service for VoteMarket campaign interactions

This service handles:
1. Fetching campaign data from on-chain contracts
2. Calculating campaign lifecycle status (active/closable/closed)
3. Checking proof insertion status for rewards claiming
4. Parallel batch fetching for performance optimization
5. LaPoste token wrapping/unwrapping detection
6. Campaign efficiency calculations

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
- Calculates efficiency parameters
"""

import asyncio
import time
import json
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from eth_utils.address import to_checksum_address
from web3 import Web3

from votemarket_toolkit.campaigns.models import (
    Campaign,
    CampaignStatus,
    Platform,
)
from votemarket_toolkit.contracts.reader import ContractReader
from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.services.laposte_service import laposte_service
from votemarket_toolkit.shared.services.resource_manager import (
    resource_manager,
)
from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.utils.campaign_utils import get_closability_info
from votemarket_toolkit.utils.pricing import get_erc20_prices_in_usd


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
        # Simple TTL cache (1 hour)
        self._ttl_cache: Dict[str, tuple] = {}
        self._ttl = 3600  # 1 hour

        # Protocol configurations for efficiency calculations
        # Based on VoteMarket V2 UI metadata files
        self.PROTOCOL_CONFIG = {
            "curve": {
                "controller": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
                "emission_token": "0xD533a949740bb3306d119CC777fa900bA034cd52",  # CRV
                "controller_method": "get_total_weight",
                "emission_method": "rate",
                "scale_factor": 10**36,
                "chain_id": 1,
            },
            "balancer": {
                "controller": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
                "emission_token": "0xba100000625a3754423978a60c9317c58a424e3D",  # BAL
                "controller_method": "get_total_weight",
                "emission_method": "rate",  # Same as Curve
                "token_admin": "0xf302f9F50958c5593770FDf4d4812309fF77414f",
                "scale_factor": 10**18,
                "chain_id": 1,
            },
            "fxn": {
                "controller": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
                "emission_token": "0x365AccFCa291e7D3914637ABf1F7635dB165Bb09",  # FXN
                "controller_method": "get_total_weight",
                "emission_method": "rate",
                "scale_factor": 10**36,
                "chain_id": 1,
            },
            "pendle": {
                "controller": "0x44087E105137a5095c008AaB6a6530182821F2F0",
                "emission_token": "0x808507121B80c02388fAd14726482e061B8da827",  # PENDLE
                "ve_token": "0x4f30A9D41B80ecC5B94306AB4364951AE3170210",  # vePENDLE
                "controller_method": "pendlePerSec",
                "ve_method": "totalSupplyAt",
                "scale_factor": 10**18,
                "chain_id": 1,
            },
            "frax": {
                "controller": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
                "emission_token": "0x3432B6A60D23Ca0dFCa7761B7ab56459D9C964D0",  # FXS
                "controller_method": "get_total_weight",
                "emission_method": "rate",
                "scale_factor": 10**36,
                "chain_id": 1,
                "fixed_weekly_rate": 0,  # FRAX emissions have ended
            },
        }

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

    def _get_cache_path(self, key: str):
        """Get the file path for a cache key."""
        import hashlib

        cache_dir = Path(".cache")
        cache_dir.mkdir(exist_ok=True)

        # Create safe filename from key
        safe_key = hashlib.sha256(f"campaigns:{key}".encode()).hexdigest()
        return cache_dir / f"{safe_key}.cache"

    def _get_ttl_cache_key(self, key: str) -> Optional[Any]:
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            value, expiry = data["value"], data["expiry"]
            if time.time() < expiry:
                return value
            cache_path.unlink(missing_ok=True)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        return None

    def _set_ttl_cache(self, key: str, value: Any) -> None:
        """Set value in TTL cache."""
        cache_path = self._get_cache_path(key)

        try:
            with open(cache_path, "w") as f:
                json.dump({"value": value, "expiry": time.time() + self._ttl}, f)
        except (OSError, TypeError):
            # If write fails (including non-serializable data), clean up
            if cache_path.exists():
                cache_path.unlink(missing_ok=True)

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

    # -----------------------------
    # Batch sizing helpers
    # -----------------------------
    def _determine_campaign_fetch_batch_size(self, total_campaigns: int) -> int:
        """Determine batch size for generic campaign fetching.

        Mirrors the sizing logic used in get_campaigns.
        """
        if total_campaigns > 400:
            return 30
        if total_campaigns > 200:
            return 25
        if total_campaigns > 100:
            return 20
        if total_campaigns > 50:
            return 15
        return max(1, min(10, total_campaigns))

    def _determine_active_ids_batch_size(self, total_campaigns: int) -> int:
        """Determine batch size for active campaign id discovery.

        Mirrors the sizing logic used in get_active_campaigns.
        """
        if total_campaigns > 300:
            return 100
        if total_campaigns > 100:
            return 150
        return total_campaigns

    # -----------------------------
    # Proof status helpers
    # -----------------------------
    async def _populate_proof_status_flags(
        self,
        campaigns: List[Dict],
        web3_service: Web3Service,
        platform_contract,
    ) -> None:
        """Populate block/point proof flags on campaigns' periods.

        This performs a gauge-level proof check (no user addresses) across
        recent periods and annotates the in-memory campaign structures.
        """
        if not campaigns:
            return

        loop = asyncio.get_running_loop()

        try:
            # Get oracle address through lens contract
            oracle_lens_address = await loop.run_in_executor(
                None, platform_contract.functions.ORACLE().call
            )
            oracle_lens_contract = web3_service.get_contract(
                to_checksum_address(oracle_lens_address),
                "lens_oracle",
            )
            oracle_address = await loop.run_in_executor(
                None, oracle_lens_contract.functions.oracle().call
            )
            oracle_contract = web3_service.get_contract(
                to_checksum_address(oracle_address),
                "oracle",
            )
            block_cache: Dict[int, Dict[str, Any]] = {}

            # Load bytecode
            proof_bytecode = resource_manager.load_bytecode("GetInsertedProofs")

            for campaign in campaigns:
                if not campaign.get("periods"):
                    continue

                gauge = campaign["campaign"]["gauge"]
                # Limit epochs to first 10 to reduce RPC load
                epochs = [p["timestamp"] for p in campaign["periods"][:10]]
                if not epochs:
                    continue

                try:
                    tx = self.contract_reader.build_get_inserted_proofs_constructor_tx(
                        {"bytecode": proof_bytecode},
                        oracle_address,
                        gauge,
                        [],
                        epochs,
                    )
                    result = await loop.run_in_executor(
                        None, web3_service.w3.eth.call, tx
                    )
                    epoch_results = self.contract_reader.decode_inserted_proofs(result)

                    # Annotate each period with proof flags
                    for period in campaign["periods"]:
                        epoch_result = next(
                            (er for er in epoch_results if er["epoch"] == period["timestamp"]),
                            None,
                        )
                        if not epoch_result:
                            continue

                        point_inserted = any(
                            pd["is_updated"] for pd in epoch_result.get("point_data_results", [])
                        )
                        period["point_data_inserted"] = point_inserted
                        period["block_updated"] = epoch_result.get("is_block_updated", False)
                        if period["block_updated"]:
                            block_info = block_cache.get(period["timestamp"])
                            if block_info is None:
                                try:
                                    block_header = await loop.run_in_executor(
                                        None,
                                        oracle_contract.functions.epochBlockNumber(period["timestamp"]).call
                                    )
                                    block_info = {
                                        "block_number": block_header[2],
                                        "block_hash": block_header[0].hex()
                                        if hasattr(block_header[0], "hex")
                                        else block_header[0],
                                        "block_timestamp": block_header[3],
                                    }
                                except Exception:
                                    block_info = {}
                                block_cache[period["timestamp"]] = block_info

                            if block_info:
                                period["block_number"] = block_info.get("block_number")
                                period["block_hash"] = block_info.get("block_hash")
                                period["block_timestamp"] = block_info.get("block_timestamp")
                except Exception:
                    # Skip proof flags for this campaign on error
                    continue
        except Exception:
            # Silently ignore proof status enrichment errors
            return

    # -----------------------------
    # Campaign fetching helpers
    # -----------------------------
    async def _fetch_campaign_batches(
        self,
        web3_service: Web3Service,
        bytecode_data: Dict[str, Any],
        platform_address: str,
        total_campaigns: int,
        campaign_id: Optional[int],
        parallel_requests: int,
    ) -> Tuple[List[Dict], int]:
        """Fetch campaigns in batches with retry and parallelization.

        Returns tuple of (campaigns, errors_count).
        """
        errors_count = 0

        async def fetch_batch(start_idx: int, limit: int, retry_count: int = 0) -> List[Dict]:
            nonlocal errors_count
            try:
                tx = self.contract_reader.build_get_campaigns_with_periods_constructor_tx(
                    bytecode_data,
                    [platform_address, start_idx, limit],
                )
                result = await asyncio.get_running_loop().run_in_executor(
                    None,
                    web3_service.w3.eth.call,
                    tx,  # type: ignore
                )
                return self.contract_reader.decode_campaign_data(result)
            except Exception:
                if retry_count < 2 and limit > 1:
                    mid_point = limit // 2
                    results1 = await fetch_batch(start_idx, mid_point, retry_count + 1)
                    results2 = await fetch_batch(start_idx + mid_point, limit - mid_point, retry_count + 1)
                    return results1 + results2
                errors_count += 1
                return []

        tasks: List[Any] = []
        if campaign_id is not None:
            tasks.append(fetch_batch(campaign_id, 1))
            effective_parallel = 1
        else:
            batch_size = self._determine_campaign_fetch_batch_size(total_campaigns)
            effective_parallel = parallel_requests
            for start_idx in range(0, total_campaigns, batch_size):
                limit = min(batch_size, total_campaigns - start_idx)
                tasks.append(fetch_batch(start_idx, limit))

        all_campaigns: List[Dict] = []
        for i in range(0, len(tasks), effective_parallel):
            chunk = tasks[i : i + effective_parallel]
            results = await asyncio.gather(*chunk, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_campaigns.extend(result)

        return all_campaigns, errors_count

    async def _get_active_campaign_ids(
        self,
        web3_service: Web3Service,
        platform_address: str,
        total_campaigns: int,
    ) -> List[int]:
        """Return active campaign IDs using the optimized bytecode approach."""
        active_ids_bytecode = resource_manager.load_bytecode("GetActiveCampaignIds")
        active_campaign_ids: List[int] = []

        batch_size = self._determine_active_ids_batch_size(total_campaigns)
        if batch_size < total_campaigns:
            tasks = []

            async def check_batch(start: int, size: int) -> List[int]:
                try:
                    tx = self.contract_reader.build_get_active_campaign_ids_constructor_tx(
                        {"bytecode": active_ids_bytecode}, platform_address, start, size
                    )
                    result = await asyncio.get_running_loop().run_in_executor(
                        None,
                        web3_service.w3.eth.call,
                        tx,
                    )
                    batch_data = self.contract_reader.decode_active_campaign_ids(result)
                    return batch_data["campaign_ids"]
                except Exception:
                    return []

            for start_id in range(0, total_campaigns, batch_size):
                tasks.append(check_batch(start_id, batch_size))

            results = await asyncio.gather(*tasks)
            for batch_ids in results:
                active_campaign_ids.extend(batch_ids)
        else:
            try:
                tx = self.contract_reader.build_get_active_campaign_ids_constructor_tx(
                    {"bytecode": active_ids_bytecode}, platform_address, 0, total_campaigns
                )
                result = await asyncio.get_running_loop().run_in_executor(
                    None,
                    web3_service.w3.eth.call,
                    tx,
                )
                batch_data = self.contract_reader.decode_active_campaign_ids(result)
                active_campaign_ids = batch_data["campaign_ids"]
            except Exception:
                return []

        return active_campaign_ids

    async def _fetch_campaigns_by_ids(
        self,
        web3_service: Web3Service,
        platform_address: str,
        campaign_ids: List[int],
    ) -> List[Dict]:
        """Fetch full campaign details for the provided ids in parallel."""
        if not campaign_ids:
            return []

        bytecode_data = resource_manager.load_bytecode("BatchCampaignsWithPeriods")

        # Use semaphore to limit concurrency instead of custom ThreadPoolExecutor
        semaphore = asyncio.Semaphore(50)

        async def fetch_one(campaign_id: int) -> Optional[Dict]:
            async with semaphore:
                try:
                    tx = self.contract_reader.build_get_campaigns_with_periods_constructor_tx(
                        bytecode_data,
                        [platform_address, campaign_id, 1],
                    )
                    result = await asyncio.get_running_loop().run_in_executor(
                        None,  # Use default executor - properly managed by asyncio
                        web3_service.w3.eth.call,
                        tx,
                    )
                    campaigns = self.contract_reader.decode_campaign_data(result)
                    return campaigns[0] if campaigns else None
                except Exception:
                    return None

        tasks = [fetch_one(cid) for cid in campaign_ids]
        results = await asyncio.gather(*tasks)
        return [c for c in results if c is not None]

    async def get_campaigns(
        self,
        chain_id: int,
        platform_address: str,
        campaign_id: Optional[int] = None,
        check_proofs: bool = False,
        parallel_requests: int = 16,
        active_only: bool = False,
    ) -> List[Campaign]:
        """
        Get campaigns with periods and optional proof checking.

        This method uses an optimized batch fetching strategy:
        1. Deploys bytecode to fetch multiple campaigns in a single call
        2. Uses adaptive parallelism based on total campaign count
        3. Optionally checks proof insertion status via oracle

        Batch Size Strategy (conservative for better reliability):
        - >400 campaigns: batch_size=50
        - >200 campaigns: batch_size=40
        - >100 campaigns: batch_size=30
        - >50 campaigns: batch_size=25
        - <=50 campaigns: batch_size=20 or less

        Parallelism is controlled by the parallel_requests parameter (default: 16).
        Failed batches are automatically retried by splitting them in half.

        Args:
            chain_id: Chain ID to query (1 for Ethereum, 42161 for Arbitrum)
            platform_address: VoteMarket platform contract address
            campaign_id: Specific campaign ID to fetch (None fetches all)
            check_proofs: Whether to check proof insertion status (adds oracle queries)
            parallel_requests: Maximum number of concurrent requests (default 32)

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
        # Check cache for full campaign fetches (not specific IDs or proof checks)
        if campaign_id is None and not check_proofs:
            cache_key = f"campaigns:{chain_id}:{platform_address}"
            cached_result = self._get_ttl_cache_key(cache_key)
            if cached_result is not None:
                return cached_result

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
                    result = await asyncio.get_running_loop().run_in_executor(
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

            # Fetch all campaigns via helper
            all_campaigns, errors_count = await self._fetch_campaign_batches(
                web3_service=web3_service,
                bytecode_data=bytecode_data,
                platform_address=platform_address,
                total_campaigns=total_campaigns,
                campaign_id=campaign_id,
                parallel_requests=parallel_requests,
            )
            # Only log if there were errors
            success_count = len(all_campaigns)
            if errors_count > 0:
                chain_name = {1: "Ethereum", 10: "Optimism", 137: "Polygon", 8453: "Base", 42161: "Arbitrum"}.get(
                    chain_id, f"Chain {chain_id}"
                )
                print(
                    f"Warning: Fetched {success_count}/{total_campaigns} campaigns from {chain_name} "
                    f"({errors_count} failed batches, will retry)"
                )

            # Optionally check proof insertion status for reward claiming
            # This verifies if the oracle has received the necessary proofs
            # for users to be able to claim their rewards
            if check_proofs and all_campaigns:
                await self._populate_proof_status_flags(all_campaigns, web3_service, platform_contract)

            # Fetch token information (both native and receipt tokens)
            await self._enrich_token_information(all_campaigns, chain_id)

            # Calculate status info for each campaign
            self._enrich_status_info(all_campaigns)

            # Filter for active campaigns only if requested
            if active_only:
                all_campaigns = [
                    c
                    for c in all_campaigns
                    if not c.get("is_closed", False)
                    and c.get("remaining_periods", 0) > 0
                ]

            # Cache the result for full fetches
            if campaign_id is None and not check_proofs and all_campaigns:
                cache_key = f"campaigns:{chain_id}:{platform_address}"
                if active_only:
                    cache_key += ":active"
                self._set_ttl_cache(cache_key, all_campaigns)

            return all_campaigns

        except Exception as e:
            print(f"Error getting campaigns: {str(e)}")
            return []

    async def get_active_campaigns(
        self,
        chain_id: int,
        platform_address: str,
        parallel_requests: int = 16,
        check_proofs: bool = False,
    ) -> List[Campaign]:
        """
        Get only active campaigns using a two-phase optimized approach.

        This method drastically reduces fetching time by:
        1. First identifying which campaigns are active (minimal data)
        2. Then fetching full details only for active campaigns

        This is much faster than fetching all campaigns and filtering.

        Args:
            chain_id: Chain ID to query
            platform_address: VoteMarket platform contract address
            parallel_requests: Number of parallel requests (default: 16)
            check_proofs: Whether to check proof insertion status

        Returns:
            List of active campaigns with full details

        Example:
            >>> service = CampaignService()
            >>> active = await service.get_active_campaigns(
            ...     chain_id=42161,
            ...     platform_address="0x8c2c..."
            ... )
            >>> print(f"Found {len(active)} active campaigns")
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

            # Get total campaign count
            total_campaigns = (
                platform_contract.functions.campaignCount().call()
            )
            if total_campaigns == 0:
                return []

            # Phase 1: Get active campaign IDs via helper
            active_campaign_ids = await self._get_active_campaign_ids(
                web3_service=web3_service,
                platform_address=platform_address,
                total_campaigns=total_campaigns,
            )

            if not active_campaign_ids:
                return []

            # Phase 2: Fetch full details only for active campaigns
            active_campaigns = await self._fetch_campaigns_by_ids(
                web3_service=web3_service,
                platform_address=platform_address,
                campaign_ids=active_campaign_ids,
            )

            # Enrich with token information
            await self._enrich_token_information(active_campaigns, chain_id)
            self._enrich_status_info(active_campaigns)

            # Optionally annotate proof flags similar to get_campaigns
            if check_proofs and active_campaigns:
                await self._populate_proof_status_flags(
                    active_campaigns, web3_service, platform_contract
                )

            return active_campaigns

        except Exception as e:
            print(f"Error getting active campaigns: {str(e)}")
            return []

    async def get_campaigns_by_manager(
        self,
        protocol: str,
        manager_address: str,
        active_only: bool = True,
    ) -> Dict[str, List[Campaign]]:
        """
        Get all campaigns managed by a specific address across all platforms.

        This method efficiently fetches campaigns from all platforms of a protocol
        and filters by manager address. Results are cached for better performance.

        Args:
            protocol: Protocol name ("curve", "balancer", "frax", "fxn", "pendle")
            manager_address: Manager wallet address to filter by
            active_only: Only check active platforms (default: True)

        Returns:
            Dictionary mapping platform key to list of campaigns managed by the address

        Example:
            >>> service = CampaignService()
            >>> results = await service.get_campaigns_by_manager(
            ...     protocol="curve",
            ...     manager_address="0x123...",
            ...     active_only=True
            ... )
            >>> for platform, campaigns in results.items():
            ...     print(f"{platform}: {len(campaigns)} campaigns")
        """
        from votemarket_toolkit.shared import registry

        results = {}
        manager_lower = manager_address.lower()

        # Get all platforms for the protocol
        platforms = registry.get_all_platforms(protocol)

        # Filter to active platforms if requested
        if active_only:
            # Active platforms based on current data
            active_platforms = {
                (
                    42161,
                    "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",
                ),  # Arbitrum v2
                (
                    42161,
                    "0x5e5C0056c6aBa37c49c5DEB0C5550AEc5C14f81e5",
                ),  # Arbitrum v2_old
                (8453, "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5"),  # Base
            }
            platforms = [
                p
                for p in platforms
                if (p["chain_id"], p["address"]) in active_platforms
            ]

        # Chain names for display
        chain_names = {
            1: "Ethereum",
            10: "Optimism",
            137: "Polygon",
            8453: "Base",
            42161: "Arbitrum",
        }

        # Fetch from each platform
        for platform in platforms:
            chain_id = platform["chain_id"]
            platform_address = platform["address"]
            chain_name = chain_names.get(chain_id, f"Chain {chain_id}")

            try:
                # Fetch all campaigns (will use cache if available)
                all_campaigns = await self.get_campaigns(
                    chain_id=chain_id,
                    platform_address=platform_address,
                    check_proofs=False,
                )

                # Filter by manager
                manager_campaigns = [
                    c
                    for c in all_campaigns
                    if c.get("campaign", {}).get("manager", "").lower()
                    == manager_lower
                ]

                if manager_campaigns:
                    platform_key = f"{chain_name} ({platform_address[:6]}...{platform_address[-4:]})"
                    results[platform_key] = manager_campaigns

            except Exception as e:
                print(f"Error fetching from {chain_name}: {str(e)}")

        return results

    async def get_active_campaigns_by_protocol(
        self,
        protocol: str,
        chain_id: int,
        check_proofs: bool = False,
        parallel_requests: int = 16,
    ) -> List[Campaign]:
        """
        Get active campaigns for a specific protocol and chain.

        This is a convenience method that automatically gets the platform address
        from the registry and fetches active campaigns.

        Args:
            protocol: Protocol name ("curve", "balancer", "frax", "fxn", "pendle")
            chain_id: Chain ID to query
            check_proofs: Whether to check proof insertion status
            parallel_requests: Number of parallel requests (default: 16)

        Returns:
            List of active campaigns

        Example:
            >>> service = CampaignService()
            >>> campaigns = await service.get_active_campaigns_by_protocol(
            ...     protocol="curve",
            ...     chain_id=42161,
            ...     check_proofs=True
            ... )
        """
        # Get platform address from registry (try v2 first, then v2_old)
        platform_address = registry.get_platform(protocol, chain_id, "v2")
        if not platform_address:
            platform_address = registry.get_platform(protocol, chain_id, "v2_old")
        if not platform_address:
            platform_address = registry.get_platform(protocol, chain_id, "v1")

        if not platform_address:
            raise Exception(
                f"No platform found for {protocol} on chain {chain_id}"
            )

        # Fetch active campaigns
        return await self.get_active_campaigns(
            chain_id=chain_id,
            platform_address=platform_address,
            parallel_requests=parallel_requests,
            check_proofs=check_proofs,
        )

    def _enrich_status_info(self, campaigns: List[Dict]) -> None:
        """
        Add status_info to each campaign with closability information.

        Args:
            campaigns: List of campaign dictionaries to enrich
        """
        current_timestamp = int(time.time())

        for campaign in campaigns:
            # Get closability info
            closability = get_closability_info(campaign)

            # Determine status
            if campaign["is_closed"]:
                status = CampaignStatus.CLOSED
            elif campaign.get("remaining_periods", 0) > 0:
                status = CampaignStatus.ACTIVE
            elif campaign["campaign"]["end_timestamp"] < current_timestamp:
                # Check if it's closable
                if closability["is_closable"]:
                    if closability["can_be_closed_by"] == "Manager Only":
                        status = CampaignStatus.CLOSABLE_BY_MANAGER
                    else:
                        status = CampaignStatus.CLOSABLE_BY_EVERYONE
                else:
                    status = CampaignStatus.NOT_CLOSABLE  # In claim period
            else:
                status = CampaignStatus.ACTIVE

            # Build status_info
            campaign["status_info"] = {
                "status": status.value,
                "is_closed": campaign["is_closed"],
                "can_close": closability["is_closable"],
                "who_can_close": (
                    closability.get("can_be_closed_by") or "no_one"
                )
                .lower()
                .replace(" ", "_"),
                "days_until_public_close": closability.get(
                    "days_until_anyone_can_close"
                ),
                "reason": closability["closability_status"],
            }

    # -----------------------------
    # Token enrichment helpers
    # -----------------------------
    def _collect_unique_reward_tokens(self, campaigns: List[Campaign]) -> List[str]:
        return list(
            set(
                c["campaign"]["reward_token"]
                for c in campaigns
                if c.get("campaign", {}).get("reward_token")
            )
        )

    async def _build_token_mapping(
        self, chain_id: int, unique_tokens: List[str]
    ) -> Dict[str, Optional[str]]:
        native_tokens = await laposte_service.get_native_tokens(chain_id, unique_tokens)
        return dict(zip(unique_tokens, native_tokens))

    def _build_all_tokens_to_fetch(
        self,
        chain_id: int,
        unique_tokens: List[str],
        native_tokens: List[Optional[str]],
    ) -> List[Dict[str, Any]]:
        all_tokens_to_fetch: List[Dict[str, Any]] = []

        for token in unique_tokens:
            if token:
                all_tokens_to_fetch.append(
                    {
                        "address": token,
                        "chain_id": chain_id,
                        "is_native": False,
                        "original_chain_id": chain_id,
                    }
                )

        for i, native_token in enumerate(native_tokens):
            if native_token and native_token.lower() != unique_tokens[i].lower():
                all_tokens_to_fetch.append(
                    {
                        "address": native_token,
                        "chain_id": chain_id,
                        "is_native": True,
                        "original_chain_id": chain_id,
                    }
                )

        return all_tokens_to_fetch

    async def _fetch_token_info_cache(
        self, all_tokens_to_fetch: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        token_info_cache: Dict[str, Dict[str, Any]] = {}
        if not all_tokens_to_fetch:
            return token_info_cache

        tasks = [
            laposte_service.get_token_info(
                t["chain_id"], t["address"], t["is_native"], t["original_chain_id"]
            )
            for t in all_tokens_to_fetch
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                continue
            token_address = all_tokens_to_fetch[i]["address"]
            token_info_cache[token_address.lower()] = result  # type: ignore
        return token_info_cache

    async def _enrich_token_prices(
        self,
        token_info_cache: Dict[str, Dict[str, Any]],
        all_tokens_to_fetch: List[Dict[str, Any]],
        chain_id: int,
    ) -> None:
        if not token_info_cache:
            return

        receipt_token_infos: List[Dict[str, Any]] = []
        native_token_infos: List[Dict[str, Any]] = []

        for token_to_fetch in all_tokens_to_fetch:
            token_addr_lower = token_to_fetch["address"].lower()
            if token_addr_lower in token_info_cache:
                token_info = token_info_cache[token_addr_lower]
                if token_to_fetch["is_native"]:
                    native_token_infos.append(token_info)
                else:
                    receipt_token_infos.append(token_info)

        if receipt_token_infos:
            await laposte_service.enrich_token_prices(receipt_token_infos, chain_id)

        if native_token_infos:
            # Mainnet prices are generally more liquid/reliable
            await laposte_service.enrich_token_prices(native_token_infos, 1)

    def _apply_token_info_to_campaigns(
        self,
        campaigns: List[Campaign],
        token_info_cache: Dict[str, Dict[str, Any]],
        token_mapping: Dict[str, Optional[str]],
        chain_id: int,
    ) -> None:
        for campaign in campaigns:
            reward_token = campaign["campaign"].get("reward_token")
            if not reward_token:
                continue

            reward_token_lower = reward_token.lower()
            native_token = token_mapping.get(reward_token, reward_token)
            native_token_lower = native_token.lower() if native_token else reward_token_lower

            receipt_info = token_info_cache.get(
                reward_token_lower,
                {
                    "name": "Unknown",
                    "symbol": "???",
                    "address": reward_token,
                    "decimals": 18,
                    "chain_id": chain_id,
                    "price": 0.0,
                },
            )

            if native_token_lower != reward_token_lower:
                native_info = token_info_cache.get(native_token_lower, receipt_info)
            else:
                native_info = receipt_info

            campaign["receipt_reward_token"] = receipt_info
            campaign["reward_token"] = native_info

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
        unique_tokens = self._collect_unique_reward_tokens(campaigns)

        if not unique_tokens:
            return

        try:
            # Build mapping and fetch plan
            token_mapping = await self._build_token_mapping(chain_id, unique_tokens)
            native_tokens = [token_mapping[t] for t in unique_tokens]
            all_tokens_to_fetch = self._build_all_tokens_to_fetch(
                chain_id, unique_tokens, native_tokens
            )

            # Fetch token infos and enrich prices
            token_info_cache = await self._fetch_token_info_cache(all_tokens_to_fetch)
            await self._enrich_token_prices(
                token_info_cache, all_tokens_to_fetch, chain_id
            )

            # Apply info to campaigns
            self._apply_token_info_to_campaigns(
                campaigns, token_info_cache, token_mapping, chain_id
            )

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

            result = await asyncio.get_running_loop().run_in_executor(
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

    def get_token_per_vetoken(self, protocol: str = "curve") -> float:
        """
        Calculate tokenPerVeToken using VoteMarket's formula for any protocol.

        Each protocol has different formulas:
        - Curve/Frax/FXN: (weeklyRate * 1e36) / totalWeight / 1e18
        - Balancer: (weeklyRate * 1e18) / totalWeight / 1e18
        - Pendle: (weeklyRate * 1e18) / totalSupply / 1e18

        Args:
            protocol: Protocol name ("curve", "balancer", "fxn", "pendle", "frax")

        Returns:
            float: Token emissions per veToken per week
        """
        if protocol not in self.PROTOCOL_CONFIG:
            raise ValueError(f"Protocol {protocol} not supported")

        config = self.PROTOCOL_CONFIG[protocol]
        web3_service = self.get_web3_service(config["chain_id"])
        w3 = web3_service.w3

        seconds_per_week = 86400 * 7

        if protocol == "pendle":
            # Pendle uses different approach: pendlePerSec and vePENDLE totalSupply
            controller_abi = [
                {
                    "name": config["controller_method"],
                    "outputs": [{"type": "uint256"}],
                    "inputs": [],
                    "stateMutability": "view",
                    "type": "function",
                }
            ]
            controller = w3.eth.contract(
                address=Web3.to_checksum_address(config["controller"]),
                abi=controller_abi,
            )
            rate_per_second = controller.functions.pendlePerSec().call()

            # Get vePENDLE total supply at current epoch
            ve_abi = [
                {
                    "name": "totalSupplyAt",
                    "outputs": [{"type": "uint128"}],
                    "inputs": [{"type": "uint128", "name": "timestamp"}],
                    "stateMutability": "view",
                    "type": "function",
                }
            ]
            ve_token = w3.eth.contract(
                address=Web3.to_checksum_address(config["ve_token"]),
                abi=ve_abi,
            )
            # Get current week timestamp
            current_timestamp = int(time.time())
            current_week = (
                current_timestamp // seconds_per_week
            ) * seconds_per_week
            total_supply = ve_token.functions.totalSupplyAt(
                current_week
            ).call()

            # Calculate weekly rate
            weekly_rate = rate_per_second * seconds_per_week

            # Apply Pendle scaling (1e18 factor)
            scaled = (weekly_rate * config["scale_factor"]) // total_supply
            token_per_vetoken = scaled / (10**18)

        elif protocol == "balancer":
            # Balancer has a fixed emission rate
            controller_abi = [
                {
                    "name": config["controller_method"],
                    "outputs": [{"type": "uint256"}],
                    "inputs": [],
                    "stateMutability": "view",
                    "type": "function",
                }
            ]
            controller = w3.eth.contract(
                address=Web3.to_checksum_address(config["controller"]),
                abi=controller_abi,
            )
            total_weight = controller.functions.get_total_weight().call()

            # Query the Balancer token admin for the current inflation rate.
            token_admin_abi = [
                {
                    "name": "getInflationRate",
                    "outputs": [{"type": "uint256"}],
                    "inputs": [],
                    "stateMutability": "view",
                    "type": "function",
                },
                {
                    "name": "rate",
                    "outputs": [{"type": "uint256"}],
                    "inputs": [],
                    "stateMutability": "view",
                    "type": "function",
                },
            ]
            token_admin = w3.eth.contract(
                address=Web3.to_checksum_address(config["token_admin"]),
                abi=token_admin_abi,
            )

            try:
                rate_per_second = (
                    token_admin.functions.getInflationRate().call()
                )
            except Exception:
                rate_per_second = token_admin.functions.rate().call()

            if total_weight == 0:
                raise ValueError(
                    "Balancer controller returned zero total weight"
                )

            with localcontext() as ctx:
                ctx.prec = 40
                rate_decimal = Decimal(rate_per_second)
                weekly_rate = rate_decimal * Decimal(seconds_per_week)
                total_weight_decimal = Decimal(total_weight)

                # Convert both values down to token units to avoid enormous integers
                weekly_rate_tokens = weekly_rate / Decimal(10**18)
                total_weight_tokens = total_weight_decimal / Decimal(10**18)

                if total_weight_tokens == 0:
                    raise ValueError("Balancer total weight (tokens) is zero")

                token_per_vetoken_decimal = (
                    weekly_rate_tokens / total_weight_tokens
                )

            token_per_vetoken = float(token_per_vetoken_decimal)

        else:
            # Curve, FXN use similar approach
            # Get total weight from controller
            controller_abi = [
                {
                    "name": config["controller_method"],
                    "outputs": [{"type": "uint256"}],
                    "inputs": [],
                    "stateMutability": "view",
                    "type": "function",
                }
            ]
            controller = w3.eth.contract(
                address=Web3.to_checksum_address(config["controller"]),
                abi=controller_abi,
            )
            total_weight = controller.functions.get_total_weight().call()

            # Get emission rate from token
            token_abi = [
                {
                    "name": config["emission_method"],
                    "outputs": [{"type": "uint256"}],
                    "inputs": [],
                    "stateMutability": "view",
                    "type": "function",
                }
            ]
            emission_token = w3.eth.contract(
                address=Web3.to_checksum_address(config["emission_token"]),
                abi=token_abi,
            )
            rate_per_second = emission_token.functions.rate().call()

            # Calculate weekly rate
            weekly_rate = rate_per_second * seconds_per_week

            # Apply scaling formula (1e36 for Curve/FXN/Frax)
            scaled = (weekly_rate * config["scale_factor"]) // total_weight
            token_per_vetoken = scaled / (10**18)

        return token_per_vetoken

    def calculate_emission_value(
        self, protocol: str = "curve"
    ) -> Tuple[float, float, float]:
        """
        Calculate emission value as displayed in VoteMarket UI for any protocol.

        Args:
            protocol: Protocol name ("curve", "balancer", "fxn", "pendle", "frax")

        Returns:
            Tuple of (emission_value, token_per_vetoken, token_price)
        """
        if protocol not in self.PROTOCOL_CONFIG:
            raise ValueError(f"Protocol {protocol} not supported")

        config = self.PROTOCOL_CONFIG[protocol]

        # Get tokenPerVeToken for this protocol
        token_per_vetoken = self.get_token_per_vetoken(protocol)

        # Get emission token price
        prices = get_erc20_prices_in_usd(
            config["chain_id"], [(config["emission_token"], 10**18)]
        )
        token_price = prices[0][1] if prices else 1.0

        # Calculate emission value (UI formula)
        emission_value = token_per_vetoken * token_price

        return emission_value, token_per_vetoken, token_price

    def calculate_max_reward_for_efficiency(
        self,
        target_efficiency: float,
        reward_token: str,
        protocol: str = "curve",
        chain_id: int = 1,
    ) -> Dict[str, float]:
        """
        Calculate max_reward_per_vote to achieve target efficiency in UI.

        This method calculates the maximum reward per vote value needed
        to achieve a target efficiency in the VoteMarket UI. The UI uses:
        Min Efficiency = Emission Value / Max Reward

        Args:
            target_efficiency: Desired efficiency (e.g., 1.25 for 125%)
            reward_token: Address of reward token
            protocol: Protocol name ("curve", "balancer", "fxn", "pendle", "frax")
            chain_id: Chain ID for reward token price lookup (default: 1 for mainnet)

        Returns:
            Dict with calculation results:
                - token_per_vetoken: CRV emissions per veToken
                - crv_price: Current CRV price in USD
                - reward_token_price: Reward token price in USD
                - reward_token_decimals: Token decimals
                - emission_value: Calculated emission value
                - target_efficiency: Input target efficiency
                - max_reward_usd: Max reward in USD terms
                - max_reward_tokens: Max reward in token terms

        Example:
            >>> result = campaign_service.calculate_max_reward_for_efficiency(
            ...     target_efficiency=1.25,
            ...     reward_token="0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F"  # SDT
            ... )
            >>> print(f"Set max_reward_per_vote to {result['max_reward_tokens']:.6f} SDT")
        """
        # Get emission value for the protocol
        emission_value, token_per_vetoken, emission_token_price = (
            self.calculate_emission_value(protocol)
        )

        # Get reward token decimals first
        web3_service = self.get_web3_service(chain_id)
        token_abi = [
            {
                "name": "decimals",
                "outputs": [{"type": "uint8"}],
                "inputs": [],
                "stateMutability": "view",
                "type": "function",
            }
        ]

        token_contract = web3_service.w3.eth.contract(
            address=Web3.to_checksum_address(reward_token), abi=token_abi
        )

        try:
            decimals = token_contract.functions.decimals().call()
        except Exception as e:
            raise Exception("Failed to fetch token decimals", str(e))

        # Get reward token price with correct decimals
        prices = get_erc20_prices_in_usd(
            chain_id, [(reward_token, 10**decimals)]
        )
        reward_token_price = prices[0][1] if prices else 1.0

        # Calculate max reward for target efficiency
        # UI Formula: Min Efficiency = Emission Value / Max Reward
        # Therefore: Max Reward = Emission Value / Target Efficiency
        max_reward_usd = emission_value / target_efficiency
        max_reward_tokens = max_reward_usd / reward_token_price

        # Get emission token symbol for display
        emission_token_symbol = {
            "curve": "CRV",
            "balancer": "BAL",
            "fxn": "FXN",
            "pendle": "PENDLE",
            "frax": "FXS",
        }.get(protocol, "TOKEN")

        return {
            "protocol": protocol,
            "token_per_vetoken": token_per_vetoken,
            "emission_token_symbol": emission_token_symbol,
            "emission_token_price": emission_token_price,
            "reward_token_price": reward_token_price,
            "reward_token_decimals": decimals,
            "emission_value": emission_value,
            "target_efficiency": target_efficiency,
            "max_reward_usd": max_reward_usd,
            "max_reward_tokens": max_reward_tokens,
        }


# Singleton instance
campaign_service = CampaignService()
