#!/usr/bin/env python3
"""
Example: Calculate max_reward_per_vote for different protocols.

This example demonstrates how to:
- Calculate optimal reward rates for target efficiency
- Compare efficiency across different protocols
- Get emission rates and token prices

Usage:
    uv run examples/python/data/calculate_efficiency.py
"""

from web3 import Web3
from web3.exceptions import ContractLogicError

from votemarket_toolkit.campaigns.service import campaign_service


def main():
    """Calculate and display efficiency metrics for multiple protocols."""
    # Example configurations for different protocols
    examples = [
        {
            "protocol": "curve",
            "reward_token": "0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F",  # SDT
            "target_efficiency": 1.25,
        },
        {
            "protocol": "pendle",
            "reward_token": "0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F",
            "target_efficiency": 1.25,
        },
        {
            "protocol": "balancer",
            "reward_token": "0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F",
            "target_efficiency": 1.25,
        },
        {
            "protocol": "fxn",
            "reward_token": "0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F",
            "target_efficiency": 1.25,
        },
    ]

    print("VoteMarket Efficiency Calculator - Multi-Protocol")
    print("=" * 60)

    for config in examples:
        print(f"\n{config['protocol'].upper()} Protocol")
        print("-" * 40)

        try:
            # Calculate efficiency
            result = campaign_service.calculate_max_reward_for_efficiency(
                target_efficiency=config["target_efficiency"],
                reward_token=config["reward_token"],
                protocol=config["protocol"],
            )

            # Get reward token symbol
            try:
                web3_service = campaign_service.get_web3_service(1)
                token_abi = [
                    {
                        "name": "symbol",
                        "outputs": [{"type": "string"}],
                        "inputs": [],
                        "stateMutability": "view",
                        "type": "function",
                    }
                ]
                token_contract = web3_service.w3.eth.contract(
                    address=Web3.to_checksum_address(config["reward_token"]),
                    abi=token_abi,
                )
                reward_symbol = token_contract.functions.symbol().call()
            except (ContractLogicError, ValueError) as exc:
                print(f"  ⚠️ Unable to fetch token symbol: {exc}")
                reward_symbol = "TOKEN"

            # Display results
            print(f"Target Efficiency: {config['target_efficiency']}x")
            print(f"Emission Token: {result['emission_token_symbol']}")
            print(
                f"  Rate: {result['token_per_vetoken']:.6f} {result['emission_token_symbol']}/veToken/week"
            )
            print(f"  Price: ${result['emission_token_price']:.4f}")
            print(f"  Value: ${result['emission_value']:.6f}/veToken")

            print(f"Reward Token: {reward_symbol}")
            print(f"  Price: ${result['reward_token_price']:.4f}")

            # Format token amount
            if result["max_reward_tokens"] < 0.0001:
                token_display = f"{result['max_reward_tokens']:.12f}".rstrip(
                    "0"
                ).rstrip(".")
            elif result["max_reward_tokens"] < 1:
                token_display = f"{result['max_reward_tokens']:.8f}".rstrip(
                    "0"
                ).rstrip(".")
            else:
                token_display = f"{result['max_reward_tokens']:.6f}".rstrip(
                    "0"
                ).rstrip(".")

            print(
                f"\n→ Set max_reward_per_vote to: {token_display} {reward_symbol}"
            )

        except (ContractLogicError, ValueError) as exc:
            print(
                f"Error calculating efficiency for {config['protocol']}: {exc}"
            )
        except Exception:
            raise

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
