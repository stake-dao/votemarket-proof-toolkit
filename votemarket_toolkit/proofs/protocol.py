"""Canonical protocol names for controller selection and storage layouts."""

from votemarket_toolkit.shared import registry


def normalize_proof_protocol(protocol: str) -> str:
    """Validate before choosing a controller or a protocol-specific layout."""
    if not isinstance(protocol, str):
        raise ValueError("Protocol must be a string")
    canonical = protocol.strip().lower()
    if registry.get_gauge_slots(canonical) is None:
        raise ValueError(f"Unknown proof protocol: {protocol!r}")
    return canonical
