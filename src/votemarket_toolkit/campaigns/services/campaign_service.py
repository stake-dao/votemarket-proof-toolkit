import asyncio
from typing import Dict, List

from eth_utils import to_checksum_address

from votemarket_toolkit.campaigns.types import Campaign, CampaignData, Platform
from votemarket_toolkit.contracts.reader import ContractReader
from votemarket_toolkit.shared.constants import ContractRegistry
from votemarket_toolkit.shared.services.resource_manager import (
    resource_manager,
)
from votemarket_toolkit.shared.services.web3_service import Web3Service


class CampaignService:
    def __init__(self):
        self.contract_reader = ContractReader()
        self.web3_services: Dict[int, Web3Service] = {}

    def get_web3_service(self, chain_id: int) -> Web3Service:
        """Get or create Web3Service for a chain"""
        if chain_id not in self.web3_services:
            self.web3_services[chain_id] = Web3Service.get_instance(chain_id)
        return self.web3_services[chain_id]

    def _convert_campaign_data_to_campaign(
        self, campaign_data: CampaignData
    ) -> Campaign:
        """Convert raw CampaignData to Campaign type"""
        return Campaign(
            id=campaign_data["id"],
            chain_id=campaign_data["campaign"]["chain_id"],
            gauge=campaign_data["campaign"]["gauge"],
            manager=campaign_data["campaign"]["manager"],
            reward_token=campaign_data["campaign"]["reward_token"],
            is_closed=campaign_data["is_closed"],
            is_whitelist_only=campaign_data["is_whitelist_only"],
            listed_users=campaign_data["addresses"],
            period_left=campaign_data["period_left"],
            details=campaign_data["campaign"],
            current_period=campaign_data["current_period"],
        )

    async def _fetch_chain_campaigns(
        self,
        web3_service: Web3Service,
        chain_id: int,
        platform_address: str,
        start_index: int,
        limit: int,
    ) -> List[Campaign]:
        """Fetch campaigns for a specific chain in batches"""
        try:
            # Validate inputs
            if limit <= 0:
                return []

            # Load bytecode using resource manager
            bytecode_data = resource_manager.load_bytecode("BatchCampaigns")

            # Build contract call
            tx = self.contract_reader.build_get_campaigns_constructor_tx(
                bytecode_data,
                [platform_address, start_index, limit],
            )

            # Execute call
            result = web3_service.w3.eth.call(tx)

            # Decode the result using specific campaign decoder
            campaign_data_list = self.contract_reader.decode_campaign_data(result)

            # Convert CampaignData to Campaign type
            return [
                self._convert_campaign_data_to_campaign(campaign_data)
                for campaign_data in campaign_data_list
            ]

        except Exception as e:
            print(f"Error fetching campaigns for chain {chain_id}: {str(e)}")
            return []

    async def query_active_campaigns(
        self, chain_id: int, platform: str
    ) -> List[Campaign]:
        """Query active campaigns for a given chain and platform"""
        web3_service = self.get_web3_service(chain_id)
        platform_address = to_checksum_address(platform.lower())

        try:
            # Get campaign count using vm_platform ABI
            platform_contract = web3_service.get_contract(
                platform_address, "vm_platform"
            )
            campaign_count = platform_contract.functions.campaignCount().call()
            if campaign_count == 0:
                return []

            # Fetch campaigns in chunks
            CHUNK_SIZE = 20
            all_campaigns = []

            # Sequential fetching to avoid RPC overload
            for start_idx in range(0, campaign_count, CHUNK_SIZE):
                try:
                    # Calculate end index for this chunk
                    end_idx = min(start_idx + CHUNK_SIZE, campaign_count)
                    remaining = end_idx - start_idx  # This is our actual chunk size

                    chunk = await self._fetch_chain_campaigns(
                        web3_service,
                        chain_id,
                        platform_address,
                        start_idx,
                        remaining  # Pass the actual number of campaigns to fetch
                    )
                    all_campaigns.extend(chunk)
                except Exception as e:
                    print(f"Error fetching chunk from {start_idx} to {end_idx}: {str(e)}")
                    continue

                # Optional: Add a small delay between chunks to prevent rate limiting
                await asyncio.sleep(0.1)

            return all_campaigns

        except Exception as e:
            print(f"Error in query_active_campaigns: {str(e)}")
            return []

    def get_all_platforms(self, protocol: str) -> List[Platform]:
        """Get all platforms for a protocol"""
        try:
            chains = ContractRegistry.get_chains(protocol.upper())
            return [
                Platform(
                    protocol=protocol,
                    chain_id=chain_id,
                    address=ContractRegistry.get_address(
                        protocol.upper(), chain_id
                    ),
                )
                for chain_id in chains
            ]
        except ValueError:
            return []


# Create global instance
campaign_service = CampaignService()
