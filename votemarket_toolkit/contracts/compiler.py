from rich import print
from solcx import compile_source, install_solc

from votemarket_toolkit.shared.services.resource_manager import (
    resource_manager,
)

# Install specific solc versions
install_solc("0.8.19")
install_solc("0.8.26")


def compile_contract(source_path: str) -> dict:
    """Compile a single Solidity contract."""
    with open(source_path, "r") as f:
        source = f.read()

    # Determine Solidity version from pragma
    solc_version = "0.8.19"  # default
    if "pragma solidity ^0.8.26" in source:
        solc_version = "0.8.26"

    compiled = compile_source(
        source, output_values=["abi", "bin"], solc_version=solc_version
    )

    # Get the main contract (last one in the file, not interfaces)
    contract_id = None
    for key in compiled.keys():
        if "GetInsertedProofs" in key:
            contract_id = key
            break
        elif "BatchCampaignData" in key:  # The actual contract name
            contract_id = key
            break
        elif "GetCCIPFee" in key:
            contract_id = key
            break
        elif "GetTokensLaPoste" in key:
            contract_id = key
            break

    if not contract_id:
        contract_id = list(compiled.keys())[-1]  # Fallback to last contract

    return compiled[contract_id]


def main():
    contracts_dir = resource_manager.ensure_resource_dir("contracts")

    for contract_file in contracts_dir.glob("*.sol"):
        print(f"Compiling {contract_file.name}...")
        try:
            compiled = compile_contract(str(contract_file))
            resource_manager.save_bytecode(
                bytecode=compiled["bin"], contract_name=contract_file.stem
            )
            print(f"✓ Successfully compiled {contract_file.name}")
        except Exception as e:
            print(f"✗ Failed to compile {contract_file.name}: {str(e)}")


if __name__ == "__main__":
    main()
