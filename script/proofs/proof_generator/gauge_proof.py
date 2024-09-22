from typing import Tuple
from eth_abi import encode
from eth_utils import keccak
from web3 import Web3
from shared.utils import encode_rlp_proofs
from shared.constants import GaugeControllerConstants


def _encode_gauge_time(gauge: str, time: int, base_slot: int) -> bytes:
    """
    Encode gauge time data for storage position calculation.

    Args:
        gauge (str): The gauge address.
        time (int): The current period.
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
        time (int): The current period.
        base_slot (int): The base slot for point weights.

    Returns:
        int: The calculated storage position.
    """
    final_slot = keccak(_encode_gauge_time(gauge, time, base_slot))
    return int.from_bytes(final_slot, byteorder="big")


def get_gauge_time_storage_slot_pre_vyper03(
    gauge: str, time: int, base_slot: int
) -> int:
    """
    Calculate storage position for gauge time (used for Curve protocol).

    Args:
        gauge (str): The gauge address.
        time (int): The current period.
        base_slot (int): The base slot for point weights.

    Returns:
        int: The calculated storage position.
    """
    intermediate_hash = keccak(_encode_gauge_time(gauge, time, base_slot))
    final_slot = keccak(encode(["bytes32"], [intermediate_hash]))
    return int.from_bytes(final_slot, byteorder="big")


def generate_gauge_proof(
    w3: Web3, protocol: str, gauge_address: str, current_period: int, block_number: int
) -> Tuple[bytes, bytes]:
    """
    Generate gauge proof for a given protocol and gauge.

    Args:
        w3 (Web3): Web3 instance.
        protocol (str): The protocol name (e.g., "curve", "balancer").
        gauge_address (str): The gauge address.
        current_period (int): The current period, rounded down to the nearest week.
            This aligns with how the gauge controller tracks voting periods.
        block_number (int): The block number for which to generate the proof.

    Returns:
        Tuple[bytes, bytes]: The encoded RLP account proof and storage proof for the gauge.
    """
    point_weights_base_slot = GaugeControllerConstants.GAUGES_SLOTS[protocol]["point_weights"]

    position_functions = {
        "curve": get_gauge_time_storage_slot_pre_vyper03,
        "default": get_gauge_time_storage_slot,
    }

    get_position = position_functions.get(protocol, position_functions["default"])
    point_weights_position = get_position(
        w3.to_checksum_address(gauge_address.lower()),
        current_period,
        point_weights_base_slot,
    )

    slots = [w3.to_hex(point_weights_position)]

    raw_proof = w3.eth.get_proof(
        w3.to_checksum_address(GaugeControllerConstants.GAUGE_CONTROLLER[protocol].lower()),
        slots,
        block_number,
    )

    return encode_rlp_proofs(raw_proof)
