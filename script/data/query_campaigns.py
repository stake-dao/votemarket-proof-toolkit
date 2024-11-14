import asyncio
from typing import Dict, List

from eth_utils import to_checksum_address
from services.contract_reader import ContractReader
from services.web3_service import Web3Service
from shared.constants import ContractRegistry
from shared.types import Campaign, CampaignData, Platform


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
        campaign_count: int,
    ) -> List[Campaign]:
        """Fetch campaigns for a specific chain in batches"""
        try:
            campaigns: List[Campaign] = []
            batch_size = 10

            for i in range(start_index, campaign_count, batch_size):
                batch_end = min(i + batch_size, campaign_count)

                try:
                    # Build contract call
                    tx = self.contract_reader.build_constructor_tx(
                        web3_service.w3,
                        self.contract_reader.load_artifact(
                            "bytecodes/BatchCampaigns.json"
                        ),
                        [platform_address, i, batch_end - i],  # skip  # limit
                    )

                    # Execute call
                    result = web3_service.w3.eth.call(tx)

                    # Decode the result using specific campaign decoder
                    campaign_data_list = (
                        self.contract_reader.decode_campaign_data(result)
                    )

                    # Convert CampaignData to Campaign type
                    for campaign_data in campaign_data_list:
                        campaign = self._convert_campaign_data_to_campaign(
                            campaign_data
                        )
                        campaigns.append(campaign)

                    # Add a small delay between batches
                    await asyncio.sleep(0.1)

                except Exception as e:
                    print(f"Error fetching batch at index {i}: {str(e)}")
                    print(f"Transaction data: {tx}")
                    continue

            return campaigns

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
            # Get campaign count
            platform_contract = web3_service.get_contract(
                platform_address, "vm_platform"
            )
            campaign_count = platform_contract.functions.campaignCount().call()

            # Fetch campaigns
            campaigns = await self._fetch_chain_campaigns(
                web3_service, chain_id, platform_address, 0, campaign_count
            )

            return campaigns

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
