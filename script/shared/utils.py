import json
import rlp
from typing import Any, Dict
from hexbytes import HexBytes


def load_json(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r") as file:
        return json.load(file)


def pad_address(address):
    # Remove the '0x' prefix
    address = address[2:]
    # Pad the address to 64 characters with zeros
    padded_address = address.zfill(64)
    # Add the '0x' prefix back
    padded_address = "0x" + padded_address
    return padded_address


def encode_rlp_proofs(proofs):
    account_proof = list(map(rlp.decode, map(HexBytes, proofs["accountProof"])))
    storage_proofs = [
        list(map(rlp.decode, map(HexBytes, proof["proof"])))
        for proof in proofs["storageProof"]
    ]
    return rlp.encode(account_proof), rlp.encode(storage_proofs)
