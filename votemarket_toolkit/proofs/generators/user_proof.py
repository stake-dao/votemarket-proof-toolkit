"""User proof generator"""

from typing import Tuple

from eth_abi import encode
from eth_utils import keccak
from web3 import Web3

from votemarket_toolkit.shared import registry
from votemarket_toolkit.utils.blockchain import encode_rlp_proofs


def _encode_user_gauge_data(user: str, gauge: str, base_slot: int) -> bytes:
    """
    Encode user and gauge data for storage slot calculation in the gauge controller.

    Args:
        user (str): The user address.
        gauge (str): The gauge address.
        base_slot (int): The base slot for user vote or slope in the gauge controller.

    Returns:
        bytes: Encoded user and gauge data for storage slot calculation.
    """
    user_encoded = keccak(encode(["uint256", "address"], [base_slot, user]))
    return encode(["bytes32", "address"], [user_encoded, gauge])


def get_user_gauge_storage_slot(user: str, gauge: str, base_slot: int) -> int:
    """
    Calculate storage slot for user gauge data in gauge controllers (post Vyper 0.3).

    This function is used for protocols other than Curve.

    Args:
        user (str): The user address.
        gauge (str): The gauge address.
        base_slot (int): The base slot for user vote or slope in the gauge controller.

    Returns:
        int: The calculated storage slot for the user's gauge data.
    """
    final_slot = keccak(_encode_user_gauge_data(user, gauge, base_slot))
    return int.from_bytes(final_slot, byteorder="big")


def get_user_gauge_storage_slot_pendle(
    user: str, gauge: str, base_slot: int
) -> int:
    """
    Calculate storage slot for user gauge data in gauge controllers (post Vyper 0.3).

    This function is used for protocols other than Curve.

    Args:
        user (str): The user address.
        gauge (str): The gauge address.
        base_slot (int): The base slot for user vote or slope in the gauge controller.

    Returns:
        int: The calculated storage slot for the user's gauge data.
    """
    encoded_1 = keccak(encode(["address", "uint256"], [user, base_slot]))
    struct_slot_int = int.from_bytes(encoded_1, byteorder="big")

    encoded_2 = keccak(
        encode(["address", "uint256"], [gauge, struct_slot_int + 1])
    )
    final_slot = int.from_bytes(encoded_2, byteorder="big")

    return final_slot


def get_user_gauge_storage_slot_pre_vyper03(
    user: str, gauge: str, base_slot: int
) -> int:
    """
    Calculate storage slot for user gauge data in gauge controllers (pre Vyper 0.3).

    This function is used specifically for the Curve protocol.

    Args:
        user (str): The user address.
        gauge (str): The gauge address.
        base_slot (int): The base slot for user vote or slope in the gauge controller.

    Returns:
        int: The calculated storage slot for the user's gauge data.
    """
    intermediate_hash = keccak(_encode_user_gauge_data(user, gauge, base_slot))
    final_slot = keccak(encode(["bytes32"], [intermediate_hash]))
    return int.from_bytes(final_slot, byteorder="big")


def generate_user_proof(
    web_3: Web3,
    protocol: str,
    gauge_address: str,
    user: str,
    block_number: int,
) -> Tuple[bytes, bytes]:
    """
    Generate user proof for a given protocol, gauge, and user.

    Args:
        w3 (Web3): Web3 instance.
        protocol (str): The protocol name (e.g., "curve", "balancer").
        gauge_address (str): The gauge address.
        user (str): The user address.
        block_number (int): The block number for which to generate the proof.

    Returns:
        Tuple[bytes, bytes]: The encoded RLP account proof and storage proof for the user.
    """

    # Get base slots for last user vote and vote user slope
    gauge_slots = registry.get_gauge_slots(protocol)
    if not gauge_slots:
        raise ValueError(f"Unknown protocol: {protocol}")

    if protocol != "pendle":
        last_user_vote_base_slot = gauge_slots["last_user_vote"]

        # Calculate last user vote storage slot
        last_user_vote_slot = get_user_gauge_storage_slot(
            web_3.to_checksum_address(user.lower()),
            web_3.to_checksum_address(gauge_address.lower()),
            last_user_vote_base_slot,
        )

    vote_user_slope_base_slot = gauge_slots["vote_user_slope"]

    # Calculate vote user slope storage slot (different for Curve protocol)
    index_additionnal_slot = 2
    if protocol == "curve":
        vote_user_slope_slot = get_user_gauge_storage_slot_pre_vyper03(
            web_3.to_checksum_address(user.lower()),
            web_3.to_checksum_address(gauge_address.lower()),
            vote_user_slope_base_slot,
        )
    elif protocol == "pendle":
        vote_user_slope_slot = get_user_gauge_storage_slot_pendle(
            web_3.to_checksum_address(user.lower()),
            web_3.to_checksum_address(gauge_address.lower()),
            vote_user_slope_base_slot,
        )
        index_additionnal_slot = 1
    else:
        vote_user_slope_slot = get_user_gauge_storage_slot(
            web_3.to_checksum_address(user.lower()),
            web_3.to_checksum_address(gauge_address.lower()),
            vote_user_slope_base_slot,
        )

    # Calculate additional slots
    vote_user_slope_slope = vote_user_slope_slot
    vote_user_slope_end = vote_user_slope_slot + index_additionnal_slot

    # Combine all slots
    slots = [web_3.to_hex(last_user_vote_slot)] if protocol != "pendle" else []

    slots += [
        web_3.to_hex(vote_user_slope_slope),
        web_3.to_hex(vote_user_slope_end),
    ]

    # Get raw proof from the blockchain
    gauge_controller = registry.get_gauge_controller(protocol)
    if not gauge_controller:
        raise ValueError(f"No gauge controller found for protocol: {protocol}")

    raw_proof = web_3.eth.get_proof(
        web_3.to_checksum_address(gauge_controller.lower()),
        slots,
        block_number,
    )

    # Encode and return the proof
    return encode_rlp_proofs(raw_proof)
