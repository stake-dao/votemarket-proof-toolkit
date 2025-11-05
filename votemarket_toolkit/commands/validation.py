from eth_utils import is_address, to_checksum_address


def validate_eth_address(address: str, param_name: str = "address") -> str:
    """Validate and return checksum ethereum address"""
    if not address or not isinstance(address, str):
        raise ValueError(
            f"Invalid {param_name}: address must be a non-empty string"
        )
    if not is_address(address):
        raise ValueError(
            f"Invalid {param_name}: {address} is not a valid Ethereum address"
        )
    return to_checksum_address(address)


def validate_chain_id(chain_id: int) -> None:
    """Validate chain ID"""
    valid_chain_ids = {1, 10, 137, 8453, 42161, 56, 146, 252}  # Ethereum, Optimism, Polygon, Base, Arbitrum, BSC, Sonic, Fraxtal
    if chain_id not in valid_chain_ids:
        raise ValueError(
            f"Invalid chain_id: {chain_id}. Must be one of {valid_chain_ids}"
        )


def validate_protocol(protocol: str) -> str:
    """Validate and normalize protocol name"""
    valid_protocols = {"curve", "balancer", "fxn", "pendle", "frax"}
    protocol = protocol.lower()
    if protocol not in valid_protocols:
        raise ValueError(
            f"Invalid protocol: {protocol}. Must be one of {valid_protocols}"
        )
    return protocol
