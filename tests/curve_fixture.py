"""Recorded Curve proofs with fixed slots, independent of slot helpers."""

import json
from pathlib import Path
from types import SimpleNamespace

import rlp
from eth_utils import keccak
from web3 import Web3
from web3.providers import BaseProvider

from votemarket_toolkit.proofs.manager import VoteMarketProofs

FIXTURE = (
    Path(__file__).parent
    / "fixtures/batch_verifier/curve_1730937600_mpt_proof.json"
)
CONTROLLER = "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB"
GAUGE = "0x26f7786de3e6d9bd37fcf47be6f2bc455a21b74a"
USER = "0xfac2f11ba2577d5122dc1ec5301d35b16688251e"
EPOCH = 1730937600
BLOCK = 21134723
USER_SLOTS = (
    "0x932574e7ded7899e6f06e556403a0e1e6a98527c65abf840171efb71ca27f0bb",
    "0x177db78194b62d3faa4a843f54c88e74adb096e11b710a2d9ca871090ba58e75",
    "0x177db78194b62d3faa4a843f54c88e74adb096e11b710a2d9ca871090ba58e77",
)
POINT_SLOT = (
    "0x417a34ca18288c939253cc4e9712b1eb86999cfb3357eeb75749f6fa948f598e"
)
EXPECTED = (
    1720411499,
    477432996090882,
    1846454400,
    14023281402120495860208000,
)
SPELLINGS = ("curve", "CURVE", "Curve", " curve ")


def decode_proof(value):
    return rlp.decode(bytes.fromhex(value.removeprefix("0x")))


class RecordedCurveProvider(BaseProvider):
    def __init__(self):
        super().__init__()
        self.fixture = json.loads(FIXTURE.read_text())
        self.account_nodes = decode_proof(self.fixture["gc_proof"])
        account = rlp.decode(self.account_nodes[-1][1])
        self.storage_root = account[2]
        user_stacks = decode_proof(
            self.fixture["users"][USER]["storage_proof"]
        )
        point_stack = decode_proof(self.fixture["point_data_proof"])[0]
        self.proofs = dict(
            zip(
                [int(slot, 16) for slot in (*USER_SLOTS, POINT_SLOT)],
                [*user_stacks, point_stack],
            )
        )
        self.values = dict(zip(self.proofs, EXPECTED))
        self.calls = []

    def make_request(self, method, params):
        self.calls.append((method, params))
        assert method in ("eth_getProof", "eth_getStorageAt"), method
        address, requested, block = params
        assert address.lower() == CONTROLLER.lower()
        assert int(block, 16) == BLOCK
        if method == "eth_getStorageAt":
            slot = int(requested, 16)
            assert slot in self.values, "Unexpected storage slot"
            result = "0x" + self.values[slot].to_bytes(32, "big").hex()
        else:
            entries = []
            for key in requested:
                slot = int(key, 16)
                assert slot in self.proofs, "Unexpected storage slot"
                entries.append(
                    {
                        "key": "0x" + slot.to_bytes(32, "big").hex(),
                        "value": hex(self.values[slot]),
                        "proof": [
                            "0x" + rlp.encode(node).hex()
                            for node in self.proofs[slot]
                        ],
                    }
                )
            account = rlp.decode(self.account_nodes[-1][1])
            result = {
                "address": CONTROLLER,
                "balance": hex(int.from_bytes(account[1], "big")),
                "nonce": hex(int.from_bytes(account[0], "big")),
                "codeHash": "0x" + account[3].hex(),
                "storageHash": "0x" + self.storage_root.hex(),
                "accountProof": [
                    "0x" + rlp.encode(node).hex()
                    for node in self.account_nodes
                ],
                "storageProof": entries,
            }
        return {"jsonrpc": "2.0", "id": 1, "result": result}

    def manager(self):
        manager = VoteMarketProofs.__new__(VoteMarketProofs)
        manager.chain_id = 1
        manager.yb_gauges = None
        manager.web3_service = SimpleNamespace(w3=Web3(self))
        return manager


def storage_path(slot):
    return keccak(int(slot, 16).to_bytes(32, "big"))
