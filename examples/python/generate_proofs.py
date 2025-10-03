"""
Example: Generate proofs for VoteMarket claims

This example shows how to:
- Generate gauge proofs for a specific period
- Generate user proofs for claiming rewards
- Get block information for proof generation
- Save proofs in the correct format

Note: Most RPC providers only keep state for recent blocks (usually 128-1000 blocks).
If you get "distance to target block exceeds maximum" errors, use a more recent block.

Usage:
    python examples/python/generate_proofs.py
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Optional

from votemarket_toolkit.proofs import VoteMarketProofs
from votemarket_toolkit.utils import get_rounded_epoch


async def generate_gauge_proof(
    protocol: str,
    gauge_address: str,
    epoch_timestamp: int,
    block_number: int,
    chain_id: int = 1,  # Mainnet by default
) -> Optional[Dict]:
    """
    Generate a gauge proof for submitting to the oracle.

    Args:
        protocol: Protocol name (curve, balancer, etc.)
        gauge_address: The gauge contract address
        epoch_timestamp: The epoch timestamp (will be rounded to week)
        block_number: Block number for the proof
        chain_id: Chain ID (default: 1 for mainnet)

    Returns:
        Dict with proof data or None if error
    """
    rounded_epoch = get_rounded_epoch(epoch_timestamp)

    print("\nGenerating gauge proof:")
    print(f"  Protocol: {protocol}")
    print(f"  Gauge: {gauge_address[:10]}...{gauge_address[-4:]}")
    print(f"  Epoch: {rounded_epoch} (from {epoch_timestamp})")
    print(f"  Block: {block_number}")

    proof_manager = VoteMarketProofs(chain_id=chain_id)

    try:
        gauge_proof = proof_manager.get_gauge_proof(
            protocol=protocol,
            gauge_address=gauge_address,
            current_epoch=epoch_timestamp,
            block_number=block_number,
        )

        print("  ✅ Gauge proof generated successfully!")

        # Convert bytes to hex strings for JSON serialization
        def convert_proof(proof):
            if isinstance(proof, list):
                return [
                    "0x" + p.hex() if isinstance(p, bytes) else p
                    for p in proof
                ]
            elif isinstance(proof, bytes):
                return "0x" + proof.hex()
            return proof

        return {
            "protocol": protocol,
            "gauge": gauge_address,
            "epoch": rounded_epoch,
            "block": block_number,
            "gauge_controller_proof": convert_proof(
                gauge_proof["gauge_controller_proof"]
            ),
            "point_data_proof": convert_proof(gauge_proof["point_data_proof"]),
        }

    except Exception as e:
        print(f"  ❌ Error: {str(e)[:100]}")
        return None


async def generate_user_proof(
    protocol: str,
    user_address: str,
    gauge_address: str,
    block_number: int,
    chain_id: int = 1,  # Mainnet by default
) -> Optional[Dict]:
    """
    Generate a user proof for claiming rewards.

    Args:
        protocol: Protocol name
        user_address: User's address
        gauge_address: The gauge contract address
        block_number: Block number for the proof
        chain_id: Chain ID (default: 1 for mainnet)

    Returns:
        Dict with proof data or None if error
    """
    print("\nGenerating user proof:")
    print(f"  User: {user_address[:10]}...{user_address[-4:]}")
    print(f"  Gauge: {gauge_address[:10]}...{gauge_address[-4:]}")
    print(f"  Block: {block_number}")

    proof_manager = VoteMarketProofs(chain_id=chain_id)

    try:
        user_proof = proof_manager.get_user_proof(
            protocol=protocol,
            gauge_address=gauge_address,
            user=user_address,
            block_number=block_number,
        )

        print("  ✅ User proof generated successfully!")

        # Convert bytes to hex strings for JSON serialization
        def convert_proof(proof):
            if isinstance(proof, list):
                return [
                    "0x" + p.hex() if isinstance(p, bytes) else p
                    for p in proof
                ]
            elif isinstance(proof, bytes):
                return "0x" + proof.hex()
            return proof

        return {
            "protocol": protocol,
            "user": user_address,
            "gauge": gauge_address,
            "block": block_number,
            "account_proof": convert_proof(user_proof["account_proof"]),
            "storage_proof": convert_proof(user_proof["storage_proof"]),
        }

    except Exception as e:
        print(f"  ❌ Error: {str(e)[:100]}")
        return None


async def get_block_for_epoch(
    epoch_timestamp: int, chain_id: int = 1
) -> Optional[int]:
    """
    Get the appropriate block number for a given epoch.

    Args:
        epoch_timestamp: The epoch timestamp
        chain_id: Chain ID

    Returns:
        Block number or None if error
    """
    proof_manager = VoteMarketProofs(chain_id=chain_id)

    try:
        # In practice, you'd need to find the block closest to the epoch timestamp
        # For this example, we'll use a recent block
        block_info = proof_manager.get_block_info(23438749)

        dt = datetime.fromtimestamp(block_info["block_timestamp"])
        print(
            f"\nBlock {block_info['block_number']} at {dt.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return block_info["block_number"]

    except Exception as e:
        print(f"Error getting block info: {str(e)[:100]}")
        return None


async def main() -> None:
    """Run the example with sample data."""

    print("=== VoteMarket Example: Generate Proofs ===")

    # Configuration
    protocol = "curve"
    gauge_address = "0xd5f2e6612e41be48461fdba20061e3c778fe6ec4"
    user_address = "0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6"
    epoch_timestamp = 1758758400
    block_number = 23438749

    # Example 1: Generate gauge proof (for oracle submission)
    print("\nExample 1: Generate gauge proof for oracle")
    print("-" * 60)

    gauge_proof = await generate_gauge_proof(
        protocol=protocol,
        gauge_address=gauge_address,
        epoch_timestamp=epoch_timestamp,
        block_number=block_number,
    )

    if gauge_proof:
        # Save proof
        os.makedirs("output", exist_ok=True)
        filename = (
            f"output/gauge_proof_{gauge_address[:8]}_{epoch_timestamp}.json"
        )

        with open(filename, "w") as f:
            json.dump(gauge_proof, f, indent=2)

        print(f"\n  Saved to: {filename}")

    # Example 2: Generate user proof (for claiming)
    print("\n\nExample 2: Generate user proof for claiming")
    print("-" * 60)

    user_proof = await generate_user_proof(
        protocol=protocol,
        user_address=user_address,
        gauge_address=gauge_address,
        block_number=block_number,
    )

    if user_proof:
        # Save proof
        filename = f"output/user_proof_{user_address[:8]}_{block_number}.json"

        with open(filename, "w") as f:
            json.dump(user_proof, f, indent=2)

        print(f"\n  Saved to: {filename}")
        print("  This proof can be submitted on-chain to claim rewards!")

    # Example 3: Get block information
    print("\n\nExample 3: Get block information for epoch")
    print("-" * 60)

    await get_block_for_epoch(epoch_timestamp)

    print("\n✅ Example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
