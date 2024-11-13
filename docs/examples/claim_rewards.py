import sys
from pathlib import Path
from typing import List

from rich import print

# Add the script directory to Python path
script_dir = str(Path(__file__).parent.parent.parent / "script")
sys.path.insert(0, script_dir)

from eth_abi import encode
from eth_utils import function_signature_to_4byte_selector, to_checksum_address
from proofs.main import VoteMarketProofs
from shared.constants import GlobalConstants
from shared.utils import load_json
from web3 import Web3

# Initialize Web3 and constants
w3 = Web3(Web3.HTTPProvider("https://arb1.arbitrum.io/rpc"))

CHAIN_ID = 42161
MANAGER_ADDRESS = "0x8898502BA35AB64b3562aBC509Befb7Eb178D4df"
VOTEMARKET_ADDRESS = "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5"
VERIFIER_ADDRESS = "0x2Fa15A44eC5737077a747ed93e4eBD5b4960a465"
BUNDLER_ADDRESS = "0x67346f8b9B7dDA4639600C190DDaEcDc654359c8"

# Initialize contracts
votemarket_contract = w3.eth.contract(
    address=to_checksum_address(VOTEMARKET_ADDRESS),
    abi=load_json("abi/vm_platform.json"),
)

verifier_contract = w3.eth.contract(
    address=to_checksum_address(VERIFIER_ADDRESS),
    abi=load_json("abi/verifier.json"),
)

lens_address = votemarket_contract.functions.ORACLE().call()
if lens_address == "0x0000000000000000000000000000000000000000":
    raise Exception("Oracle not set on Votemarket")

lens_contract = w3.eth.contract(
    address=to_checksum_address(lens_address),
    abi=load_json("abi/oracle_lens.json"),
)

oracle_address = lens_contract.functions.oracle().call()
oracle_contract = w3.eth.contract(
    address=to_checksum_address(oracle_address),
    abi=load_json("abi/oracle.json"),
)


def to_bytes(data) -> bytes:
    """Convert data to bytes if it's a hex string, otherwise return as is"""
    if isinstance(data, str) and data.startswith("0x"):
        return bytes.fromhex(data[2:])
    if isinstance(data, str):
        return bytes.fromhex(data)
    return data  # Already bytes


def get_epoch_block_data(epoch: int) -> dict:
    """Get block data for a given epoch from Oracle"""
    block_data = oracle_contract.functions.epochBlockNumber(epoch).call()
    return {
        "blockNumber": block_data[2],  # uint256 number
        "blockHash": block_data[0],  # bytes32 hash
        "timestamp": block_data[3],  # uint256 timestamp
        "stateRoot": block_data[
            1
        ],  # bytes32 stateRootHash -> 0 if block inserted but no block proof
    }


def get_point_data(gauge_address: str, epoch: int) -> dict:
    """Get setted point data for a given gauge and epoch"""
    return oracle_contract.functions.pointByEpoch(gauge_address, epoch).call()


def get_user_data(user_address: str, gauge_address: str, epoch: int) -> dict:
    """Get setted data for a given user, gauge and epoch"""
    return oracle_contract.functions.votedSlopeByEpoch(
        user_address, gauge_address, epoch
    ).call()


def encode_proof_calls(
    verifier_address: str, proofs_needed: List[dict]
) -> bytes:
    """
    Encode multiple proof submission calls for multicall using the Bundler

    Args:
        verifier_address: Address of the verifier contract
        proofs_needed: List of proof data dictionaries
    Returns:
        Encoded multicall data
    """
    encoded_calls = []

    for proof in proofs_needed:
        if proof["type"] == "block_proof":
            # Encode setBlockData call
            selector = function_signature_to_4byte_selector(
                "setBlockData(address,bytes,bytes)"
            )
            encoded_params = encode(
                ["address", "bytes", "bytes"],
                [
                    verifier_address,
                    to_bytes(proof["block_header"]),
                    to_bytes(proof["gauge_controller_proof"]),
                ],
            )
            encoded_calls.append(selector + encoded_params)

        elif proof["type"] == "gauge_proof":
            # Encode setPointData call
            selector = function_signature_to_4byte_selector(
                "setPointData(address,address,uint256,bytes)"
            )
            encoded_params = encode(
                ["address", "address", "uint256", "bytes"],
                [
                    verifier_address,
                    proof["gauge_address"],
                    proof["epoch"],
                    to_bytes(proof["point_data_proof"]),
                ],
            )
            encoded_calls.append(selector + encoded_params)

        elif proof["type"] == "user_proof":
            # Encode setAccountData call
            selector = function_signature_to_4byte_selector(
                "setAccountData(address,address,address,uint256,bytes)"
            )
            encoded_params = encode(
                ["address", "address", "address", "uint256", "bytes"],
                [
                    verifier_address,
                    proof["user_address"],
                    proof["gauge_address"],
                    proof["epoch"],
                    to_bytes(proof["storage_proof"]),
                ],
            )
            encoded_calls.append(selector + encoded_params)

    # Encode the complete multicall
    multicall_selector = function_signature_to_4byte_selector(
        "multicall(bytes[])"
    )
    return multicall_selector + encode(["bytes[]"], [encoded_calls])


def encode_bundler_claim(
    votemarket_address: str,
    campaign_id: int,
    user_address: str,
    epoch: int,
    hook_data: bytes = b"",
) -> bytes:
    """
    Encode a claim call through the Bundler

    Args:
        votemarket_address: Address of the Votemarket contract
        campaign_id: Campaign ID
        user_address: User address
        epoch: Epoch to claim
        hook_data: Optional hook data
    Returns:
        Encoded claim call data
    """
    # Get function selector for claim(address,uint256,address,uint256,bytes)
    claim_selector = function_signature_to_4byte_selector(
        "claim(address,uint256,address,uint256,bytes)"
    )

    # Encode parameters
    encoded_params = encode(
        ["address", "uint256", "address", "uint256", "bytes"],
        [votemarket_address, campaign_id, user_address, epoch, hook_data],
    )

    return claim_selector + encoded_params


def process_claim(campaign_id: int, user_address: str, epoch: int) -> dict:
    """
    Process a claim for a given campaign, user and epoch.
    Checks both current epoch and previous epoch (epoch - WEEK).
    Returns either proof requirements or ready status.
    """
    vm_proofs = VoteMarketProofs(1)  # Data is from Ethereum Mainnet
    proofs_needed = []

    # Get campaign infos
    campaign_infos = votemarket_contract.functions.campaignById(
        campaign_id
    ).call()
    gauge_address = campaign_infos[1]

    # Process epochs in order (previous epoch first)
    epochs_to_check = [epoch - GlobalConstants.WEEK, epoch]

    for current_epoch in epochs_to_check:
        # Get block data for the epoch
        block_data = get_epoch_block_data(current_epoch)

        # If not submitted, exception
        if block_data["blockNumber"] == 0:
            raise Exception(f"Block not submitted for epoch {current_epoch}")

        # 1. Check and collect block proof if needed
        if block_data["stateRoot"] == "0x" + "0" * 64:
            print(f"Need to submit block proof for epoch {current_epoch}")
            block_info = vm_proofs.get_block_info(block_data["blockNumber"])
            gauge_proof = vm_proofs.get_gauge_proof(
                protocol="curve",
                gauge_address="0x0000000000000000000000000000000000000000",
                current_epoch=current_epoch,
                block_number=block_data["blockNumber"],
            )
            proofs_needed.append(
                {
                    "type": "block_proof",
                    "epoch": current_epoch,
                    "block_header": block_info["rlp_block_header"],
                    "gauge_controller_proof": gauge_proof[
                        "gauge_controller_proof"
                    ],
                }
            )

        # 2. Check and collect gauge proof if needed
        gauge_data = get_point_data(gauge_address, current_epoch)
        if gauge_data[1] == 0:  # lastUpdate
            print(f"Need to submit gauge proof for epoch {current_epoch}")
            gauge_proof = vm_proofs.get_gauge_proof(
                protocol="curve",
                gauge_address=gauge_address,
                epoch=current_epoch,
                block_number=block_data["blockNumber"],
            )
            proofs_needed.append(
                {
                    "type": "gauge_proof",
                    "epoch": current_epoch,
                    "gauge_address": gauge_address,
                    "point_data_proof": gauge_proof["point_data_proof"],
                }
            )

        # 3. Check and collect user proof if needed
        user_data = get_user_data(user_address, gauge_address, current_epoch)
        if user_data[3] == 0:  # lastUpdate
            print(f"Need to submit user proof for epoch {current_epoch}")
            user_proof = vm_proofs.get_user_proof(
                protocol="curve",
                gauge_address=gauge_address,
                user=user_address,
                block_number=block_data["blockNumber"],
            )
            proofs_needed.append(
                {
                    "type": "user_proof",
                    "epoch": current_epoch,
                    "user_address": user_address,
                    "gauge_address": gauge_address,
                    "storage_proof": user_proof["storage_proof"],
                }
            )

    # Return proof requirements or ready status
    if proofs_needed:
        multicall_data = encode_proof_calls(VERIFIER_ADDRESS, proofs_needed)
        return {
            "type": "proofs_needed",
            "proofs_count": len(proofs_needed),
            "transaction": multicall_data,
        }
    return {"type": "ready", "epoch": epoch, "transaction": None}


# Example usage
if __name__ == "__main__":
    from time import time

    from shared.constants import GlobalConstants

    # Calculate current epoch (rounded down to week)
    current_epoch = (
        int(time()) // GlobalConstants.WEEK
    ) * GlobalConstants.WEEK

    # Process claim for:
    # - Campaign ID: 1
    # - User: 0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6
    # - Current epoch
    result = process_claim(
        campaign_id=1,
        user_address="0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6",
        epoch=current_epoch,
    )

    print("\nClaim processing result:")
    print(f"Type: {result['type']}")

    if result["type"] == "proofs_needed":
        print(f"\nProofs needed: {result['proofs_count']}")
        print("\nMulticall transaction data for proof submission:")
        print(result["transaction"].hex())

        # Example of building the proof submission transaction
        tx = {
            "from": MANAGER_ADDRESS,
            "to": BUNDLER_ADDRESS,
            "data": result["transaction"],
            "gas": 2000000,  # Adjust as needed
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(MANAGER_ADDRESS),
        }
        print("\nProof submission transaction details:")
        print(f"To: {tx['to']}")
        print(f"Gas limit: {tx['gas']:,}")
        print(f"Nonce: {tx['nonce']}")
    else:
        print("\nAll proofs are ready - proceeding with claim!")

        # Encode claim through bundler
        claim_data = encode_bundler_claim(
            votemarket_address=VOTEMARKET_ADDRESS,
            campaign_id=1,
            user_address="0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6",
            epoch=current_epoch,
            hook_data=b"",
        )

        # Example of building the claim transaction
        tx = {
            "from": MANAGER_ADDRESS,
            "to": BUNDLER_ADDRESS,
            "data": claim_data,
            "gas": 500000,
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(MANAGER_ADDRESS),
        }
        print("\nClaim transaction details:")
        print(f"To: {tx['to']}")
        print(f"Data: {tx['data'].hex()}")
        print(f"Gas limit: {tx['gas']:,}")
        print(f"Nonce: {tx['nonce']}")
