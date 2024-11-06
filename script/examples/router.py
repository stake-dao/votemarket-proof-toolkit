"""
Build claim multicall.

This script demonstrates how to generate encoded calls for the Verifier contract
and combine them into a multicall for claiming rewards in VotemarketV2.
"""

import asyncio
from typing import Any, Dict, List

from data.main import VoteMarketData
from eth_utils import to_checksum_address
from proofs.main import VoteMarketProofs
from rich import print as rprint
from rich.panel import Panel
from shared.constants import GlobalConstants
from shared.web3_service import get_web3_service

# Initialize services
vm_proofs = VoteMarketProofs(1)
vm_votes = VoteMarketData(1)
web3_service = get_web3_service()
web3_service.add_chain(42161, GlobalConstants.get_rpc_url(42161))

# Example parameters (Arbitrum test contracts)
PROTOCOL = "curve"
USER = to_checksum_address("0xa219712cc2aaa5aa98ccf2a7ba055231f1752323")
VERIFIER_ADDRESS = to_checksum_address(
    "0x348d1bd2a18c9a93eb9ab8e5f55852da3036e225"
)
VOTEMARKET_ADDRESS = to_checksum_address(
    "0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e"
)


async def get_all_proofs(
    protocol: str, campaigns: List[Dict[str, Any]], user: str
) -> Dict[str, Any]:
    rprint(Panel("Generating Proofs", style="bold magenta"))

    all_proofs = {"block_proofs": {}, "gauge_proofs": {}, "user_proofs": {}}

    for campaign in campaigns:
        for claim_info in campaign["claimInfo"]:
            if (
                claim_info["claimable"] == "0"
                or claim_info["blockNumber"] == 0
            ):
                continue

            epoch = claim_info["epoch"]
            block_number = claim_info["blockNumber"]
            gauge_address = campaign["gauge"]

            # Get block proof
            if epoch not in all_proofs["block_proofs"]:
                block_info = vm_proofs.get_block_info(block_number)
                gauge_proof = vm_proofs.get_gauge_proof(
                    protocol, gauge_address, epoch, block_number
                )
                all_proofs["block_proofs"][epoch] = {
                    "rlp_block_header": block_info["rlp_block_header"],
                    "gauge_controller_proof": gauge_proof[
                        "gauge_controller_proof"
                    ],
                }
                rprint(
                    f"[green]Generated block proof for epoch {epoch}[/green]"
                )

            # Get gauge proof
            gauge_key = (epoch, gauge_address)
            if gauge_key not in all_proofs["gauge_proofs"]:
                gauge_proof = vm_proofs.get_gauge_proof(
                    protocol, gauge_address, epoch, block_number
                )
                all_proofs["gauge_proofs"][gauge_key] = gauge_proof[
                    "point_data_proof"
                ]
                rprint(
                    f"[green]Generated gauge proof for {gauge_address} at epoch {epoch}[/green]"
                )

            # Get user proof
            user_key = (epoch, gauge_address, user)
            if user_key not in all_proofs["user_proofs"]:
                user_proof = vm_proofs.get_user_proof(
                    protocol, gauge_address, user, block_number
                )
                all_proofs["user_proofs"][user_key] = user_proof[
                    "storage_proof"
                ]
                rprint(
                    f"[green]Generated user proof for {user} on gauge {gauge_address} at epoch {epoch}[/green]"
                )

    return all_proofs


async def build_claim_multicall(
    user: str, campaigns: List[Dict[str, Any]], all_proofs: Dict[str, Any]
) -> List[str]:
    rprint(Panel("Building Claim Multicall", style="bold magenta"))

    verifier = web3_service.get_contract(VERIFIER_ADDRESS, "verifier", 42161)
    votemarket = web3_service.get_contract(
        VOTEMARKET_ADDRESS, "vm_platform", 42161
    )
    calldatas: List[str] = []

    for campaign in campaigns:
        for claim_info in campaign["claimInfo"]:
            if (
                claim_info["claimable"] == "0"
                or claim_info["blockNumber"] == 0
            ):
                continue

            epoch = claim_info["epoch"]
            gauge_address = campaign["gauge"]

            # Encode setBlockData
            block_proof = all_proofs["block_proofs"][epoch]
            calldata = verifier.encodeABI(
                fn_name="setBlockData",
                args=[
                    block_proof["rlp_block_header"],
                    block_proof["gauge_controller_proof"],
                ],
            )
            calldatas.append(calldata)

            # Encode setPointData
            gauge_proof = all_proofs["gauge_proofs"][(epoch, gauge_address)]
            calldata = verifier.encodeABI(
                fn_name="setPointData",
                args=[gauge_address, epoch, gauge_proof],
            )
            calldatas.append(calldata)

            # Encode setAccountData
            user_proof = all_proofs["user_proofs"][
                (epoch, gauge_address, user)
            ]
            calldata = verifier.encodeABI(
                fn_name="setAccountData",
                args=[user, gauge_address, epoch, user_proof],
            )
            calldatas.append(calldata)

            # claim(uint256 campaignId, address account, uint256 epoch, bytes calldata hookData)
            # Encode claim action
            calldata = votemarket.encodeABI(
                fn_name="claim",
                args=[campaign["id"], user, epoch, b"0x"],
            )
            calldatas.append(calldata)

    rprint(
        f"[green]Generated {len(calldatas)} calldatas for multicall:[/green]"
    )
    rprint("  1. setBlockData")
    rprint("  2. setPointData")
    rprint("  3. setAccountData")
    rprint("  4. claim")
    return calldatas


def encode_multicall(calldatas: List[str]) -> str:
    router_address = "0xcE1f6A342A82391da9B15608758703dd9D837ec8"
    router = web3_service.get_contract(router_address, "router", 42161)

    multicall_data = router.encodeABI(fn_name="multicall", args=[calldatas])

    return multicall_data


async def main():
    rprint(
        Panel(
            "Starting VoteMarket Claim Multicall Generation",
            style="bold green",
        )
    )

    # Mock campaigns data
    campaigns = [
        {
            "id": 1,
            "gauge": "0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A",
            "claimInfo": [
                {
                    "epoch": 1723680000,
                    "blockNumber": 20864159,
                    "claimable": "1000000000000000000",
                    "hasBlockData": False,
                    "hasGaugeData": False,
                    "hasUserData": False,
                }
            ],
        }
    ]

    all_proofs = await get_all_proofs(PROTOCOL, campaigns, USER)
    calldatas = await build_claim_multicall(USER, campaigns, all_proofs)

    # Encode the multicall
    multicall_data = encode_multicall(calldatas)

    rprint("\n[cyan]Encoded multicall data for router:[/cyan]")
    rprint(f"[yellow]{multicall_data}[/yellow]")

    rprint("\n[cyan]Router address:[/cyan]")
    rprint("[yellow]0xcE1f6A342A82391da9B15608758703dd9D837ec8[/yellow]")

    rprint(
        Panel(
            "VoteMarket Claim Multicall Generation Completed",
            style="bold green",
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
