"""Gauge proof generator"""

from typing import Tuple

from eth_abi import encode
from eth_utils import keccak
from web3 import Web3

from votemarket_toolkit.shared import registry
from votemarket_toolkit.utils.blockchain import encode_rlp_proofs


def _encode_gauge_time(gauge: str, time: int, base_slot: int) -> bytes:
    """
    Encode gauge time data for storage position calculation.

    Args:
        gauge (str): The gauge address.
        time (int): The current epoch.
        base_slot (int): The base slot for point weights.

    Returns:
        bytes: Encoded gauge time data.
    """
    gauge_encoded = keccak(encode(["uint256", "address"], [base_slot, gauge]))
    return encode(["bytes32", "uint256"], [gauge_encoded, time])


def get_gauge_time_storage_slot(gauge: str, time: int, base_slot: int) -> int:
    """
    Calculate storage position for gauge time (used for non-Curve protocols).

    Args:
        gauge (str): The gauge address.
        time (int): The current epoch.
        base_slot (int): The base slot for point weights.

    Returns:
        int: The calculated storage position.
    """
    final_slot = keccak(_encode_gauge_time(gauge, time, base_slot))
    return int.from_bytes(final_slot, byteorder="big")


def get_gauge_time_storage_slot_pendle(
    gauge: str, time: int, base_slot: int
) -> int:
    """
    Calculate storage position for gauge time (used for Pendle protocol).

    Args:
        gauge (str): The gauge address.
        time (int): The current epoch.
        base_slot (int): The base slot for point weights.

    Returns:
        int: The calculated storage position.
    """
    encoded_1 = keccak(encode(["uint128", "uint256"], [time, base_slot]))
    struct_slot_int = int.from_bytes(encoded_1, byteorder="big")

    encoded_2 = keccak(
        encode(["address", "uint256"], [gauge, struct_slot_int + 1])
    )
    final_slot = int.from_bytes(encoded_2, byteorder="big")

    return final_slot


def get_gauge_time_storage_slot_pre_vyper03(
    gauge: str, time: int, base_slot: int
) -> int:
    """
    Calculate storage position for gauge time (used for Curve protocol).

    Args:
        gauge (str): The gauge address.
        time (int): The current epoch.
        base_slot (int): The base slot for point weights.

    Returns:
        int: The calculated storage position.
    """
    intermediate_hash = keccak(_encode_gauge_time(gauge, time, base_slot))
    final_slot = keccak(encode(["bytes32"], [intermediate_hash]))
    return int.from_bytes(final_slot, byteorder="big")


def generate_gauge_proof(
    web_3: Web3,
    protocol: str,
    gauge_address: str,
    current_epoch: int,
    block_number: int,
) -> Tuple[bytes, bytes]:
    """
    Generate gauge proof for a given protocol and gauge.

    Args:
        web_3 (Web3): Web3 instance.
        protocol (str): The protocol name (e.g., "curve", "balancer").
        gauge_address (str): The gauge address.
        current_epoch (int): The current epoch, rounded down to the nearest week.
            This aligns with how the gauge controller tracks voting periods.
        block_number (int): The block number for which to generate the proof.

    Returns:
        Tuple[bytes, bytes]: The encoded RLP account proof and storage proof for the gauge.
    """
    gauge_slots = registry.get_gauge_slots(protocol)
    if not gauge_slots:
        raise ValueError(f"Unknown protocol: {protocol}")

    point_weights_base_slot = gauge_slots["point_weights"]

    position_functions = {
        "curve": get_gauge_time_storage_slot_pre_vyper03,
        "pendle": get_gauge_time_storage_slot_pendle,
        "default": get_gauge_time_storage_slot,
    }

    get_position = position_functions.get(
        protocol, position_functions["default"]
    )
    point_weights_position = get_position(
        web_3.to_checksum_address(gauge_address.lower()),
        current_epoch,
        point_weights_base_slot,
    )

    slots = [web_3.to_hex(point_weights_position)]

    gauge_controller = registry.get_gauge_controller(protocol)
    if not gauge_controller:
        raise ValueError(f"No gauge controller found for protocol: {protocol}")

    raw_proof = web_3.eth.get_proof(
        web_3.to_checksum_address(gauge_controller.lower()),
        slots,
        block_number,
    )

    return encode_rlp_proofs(raw_proof)
