"""
Oracle service for querying canonical block numbers from VoteMarket oracle.

This service interfaces with the VoteMarket oracle contracts to get
verified block numbers for specific epochs, ensuring all participants
use the same block for merkle tree consistency.
"""

from typing import Dict, List

from eth_utils import to_checksum_address
from w3multicall.multicall import W3Multicall

from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.utils.blockchain import get_rounded_epoch


class OracleService:
    """
    Service for querying VoteMarket oracle data.

    The oracle stores canonical block numbers for each epoch to ensure
    all participants generate consistent merkle trees.
    """

    def __init__(self, chain_id: int):
        """
        Initialize the oracle service.

        Args:
            chain_id: Blockchain network ID (1 for Ethereum, 42161 for Arbitrum)
        """
        self.chain_id = chain_id
        self.web3_service = Web3Service.get_instance(chain_id)

    def get_epochs_block(
        self, chain_id: int, platform: str, epochs: List[int]
    ) -> Dict[int, int]:
        """
        Get oracle-verified block numbers for specific epochs.

        The VoteMarket oracle stores the "canonical" block number for each epoch.
        All participants must use the same block to ensure merkle tree consistency.

        Returns 0 for epochs where the oracle hasn't been updated yet.

        Args:
            chain_id: Blockchain network ID (1=Ethereum, 42161=Arbitrum)
            platform: VoteMarket platform contract address
            epochs: List of epoch timestamps to query

        Returns:
            Dict[int, int]: Mapping of epoch → block number
                           (0 means oracle not updated for that epoch)

        Example:
            >>> # Get canonical blocks for proof generation
            >>> blocks = service.get_epochs_block(
            ...     chain_id=1,
            ...     platform="0x0000000895cB182E6f983eb4D8b4E0Aa0B31Ae4c",
            ...     epochs=[1699920000, 1700524800]
            ... )
            >>> for epoch, block in blocks.items():
            ...     if block > 0:
            ...         proof = proof_manager.get_user_proof(..., block_number=block)
        """
        # Always round epochs to the day for consistency
        epochs = [get_rounded_epoch(epoch) for epoch in epochs]

        w3 = self.web3_service.w3
        multicall = W3Multicall(w3)

        # Navigate the oracle hierarchy: Platform → Lens → Oracle
        platform_contract = self.web3_service.get_contract(
            platform, "vm_platform"
        )

        # Get oracle lens address from platform
        lens = platform_contract.functions.ORACLE().call()
        lens_address = to_checksum_address(lens.lower())

        # Get actual oracle address from lens (the lens is a proxy)
        lens_contract = self.web3_service.get_contract(
            lens_address, "oracle_lens"
        )
        oracle_address = lens_contract.functions.oracle().call()
        oracle_address = to_checksum_address(oracle_address.lower())

        # If no oracle is set, return zeros for all epochs
        if oracle_address == "0x0000000000000000000000000000000000000000":
            return {epoch: 0 for epoch in epochs}

        # Build multicall queries for each epoch
        for epoch in epochs:
            multicall.add(
                W3Multicall.Call(
                    oracle_address,
                    "epochBlockNumber(uint256)(bytes32,bytes32,uint256,uint256)",
                    [epoch],
                )
            )

        # Execute all queries in a single call
        results = multicall.call()

        # Map epochs to their block numbers
        # epochBlockNumber returns (merkleRoot, ipfsHash, blockNumber, timestamp)
        # We extract blockNumber (index 2) from the result
        return {
            epochs[i]: results[i][2] if results[i][2] != 0 else 0
            for i in range(len(epochs))
        }
