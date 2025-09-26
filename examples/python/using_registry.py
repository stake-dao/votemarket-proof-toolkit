#!/usr/bin/env python3
"""
Example: Using the simplified registry to fetch VoteMarket addresses.

This script demonstrates how to use the simplified registry
to fetch VoteMarket platform addresses and configuration.
"""

from votemarket_toolkit.shared import registry


def main():
    print("VoteMarket Registry Examples")
    print("=" * 50)

    # Example 1: Get a specific VoteMarket platform address
    print("\n1. Get Curve VoteMarket V2 on Arbitrum:")
    address = registry.get_platform("curve", 42161, "v2")
    print(f"   Address: {address}")

    # Example 2: Get all platforms for a protocol
    print("\n2. Get all platforms for Curve:")
    platforms = registry.get_all_platforms("curve")
    print(f"   Found {len(platforms)} platforms:")
    for p in platforms[:3]:  # Show first 3
        print(f"   - Chain {p['chain_id']}: {p['address']} ({p['version']})")

    # Example 3: Get platforms on a specific chain
    print("\n3. Get all platforms on Arbitrum (42161):")
    platforms = registry.get_platforms_for_chain(42161)
    for p in platforms:
        print(f"   - {p['protocol']}: {p['address']} ({p['version']})")

    # Example 4: Get gauge configuration
    print("\n4. Get gauge controller and configuration:")
    controller = registry.get_gauge_controller("curve")
    slots = registry.get_gauge_slots("curve")
    print(f"   Curve controller: {controller}")
    print(f"   Curve slots: {list(slots.keys())}")

    # Example 5: Simple usage in code
    print("\n5. Using in your code:")
    print("   ```python")
    print("   from votemarket_toolkit.shared import registry")
    print("   ")
    print("   # Get platform address")
    print('   curve_v2 = registry.get_platform("curve", 42161, "v2")')
    print("   ")
    print("   # Get gauge controller")
    print('   controller = registry.get_gauge_controller("curve")')
    print("   ")
    print("   # Get all platforms for a protocol")
    print('   platforms = registry.get_all_platforms("balancer")')
    print("   ```")

    print("\n" + "=" * 50)
    print("✓ Examples completed!")


if __name__ == "__main__":
    main()
