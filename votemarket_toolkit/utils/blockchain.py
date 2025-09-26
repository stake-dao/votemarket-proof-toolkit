import rlp
from hexbytes import HexBytes

from votemarket_toolkit.shared.constants import GlobalConstants


def pad_address(address: str) -> str:
    """Pad an Ethereum address to 64 characters"""
    # Remove the '0x' prefix
    address = address[2:]
    # Pad the address to 64 characters with zeros
    padded_address = address.zfill(64)
    # Add the '0x' prefix back
    return "0x" + padded_address


def encode_rlp_proofs(proofs: dict) -> tuple[bytes, bytes]:
    """Encode RLP proofs for Ethereum storage"""
    account_proof = list(
        map(rlp.decode, map(HexBytes, proofs["accountProof"]))
    )
    storage_proofs = [
        list(map(rlp.decode, map(HexBytes, proof["proof"])))
        for proof in proofs["storageProof"]
    ]
    return rlp.encode(account_proof), rlp.encode(storage_proofs)


def get_rounded_epoch(timestamp: int) -> int:
    """Get the rounded epoch for a given timestamp"""
    return timestamp // GlobalConstants.WEEK * GlobalConstants.WEEK
