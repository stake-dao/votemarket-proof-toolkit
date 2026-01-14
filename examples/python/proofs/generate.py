#!/usr/bin/env python3
"""
Example: Generate proofs for VoteMarket claims.

This example demonstrates how to:
- Generate gauge proofs for a specific period
- Generate user proofs for claiming rewards
- Get block information for proof generation
- Save proofs in the correct format

Note: Most RPC providers only keep state for recent blocks (usually 128-1000 blocks).
If you get "distance to target block exceeds maximum" errors, use a more recent block.

Usage:
    uv run examples/python/proofs/generate.py
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Optional

from web3.exceptions import BlockNotFound, ContractLogicError

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

    result = proof_manager.get_gauge_proof(
        protocol=protocol,
        gauge_address=gauge_address,
        current_epoch=epoch_timestamp,
        block_number=block_number,
    )

    if not result.success:
        print(f"  ❌ Error: {result.errors[0].message[:100]}")
        return None

    gauge_proof = result.data
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

    result = proof_manager.get_user_proof(
        protocol=protocol,
        gauge_address=gauge_address,
        user=user_address,
        block_number=block_number,
    )

    if not result.success:
        print(f"  ❌ Error: {result.errors[0].message[:100]}")
        return None

    user_proof = result.data
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
    web3_service = proof_manager.web3_service
    web3_instance = web3_service.w3

    try:
        latest_block = web3_instance.eth.get_block("latest")
        if epoch_timestamp >= latest_block["timestamp"]:
            dt = datetime.fromtimestamp(latest_block["timestamp"])
            print(
                f"\nEpoch is in the future relative to latest block; using block {latest_block['number']} ({dt.strftime('%Y-%m-%d %H:%M:%S')})"
            )
            return latest_block["number"]

        low = 0
        high = latest_block["number"]
        closest_block = latest_block

        while low <= high:
            mid = (low + high) // 2
            block = web3_instance.eth.get_block(mid)

            if block["timestamp"] == epoch_timestamp:
                closest_block = block
                break

            if block["timestamp"] < epoch_timestamp:
                closest_block = block
                low = mid + 1
            else:
                high = mid - 1

        dt = datetime.fromtimestamp(closest_block["timestamp"])
        print(
            f"\nClosest block to epoch {epoch_timestamp}: {closest_block['number']} ({dt.strftime('%Y-%m-%d %H:%M:%S')})"
        )

        return closest_block["number"]

    except (BlockNotFound, ValueError, ContractLogicError) as exc:
        print(f"Error getting block info: {str(exc)[:100]}")
        return None
    except Exception:
        raise


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
        output_dir = os.path.abspath("output")
        os.makedirs(output_dir, exist_ok=True)

        filename = f"gauge_proof_{gauge_address[:8]}_{epoch_timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w") as f:
            json.dump(gauge_proof, f, indent=2)

        print(f"\n  Saved to: {filepath}")

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
        filename = f"user_proof_{user_address[:8]}_{block_number}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w") as f:
            json.dump(user_proof, f, indent=2)

        print(f"\n  Saved to: {filepath}")
        print("  This proof can be submitted on-chain to claim rewards!")

    # Example 3: Get block information
    print("\n\nExample 3: Get block information for epoch")
    print("-" * 60)

    await get_block_for_epoch(epoch_timestamp)

    print("\n✅ Example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
