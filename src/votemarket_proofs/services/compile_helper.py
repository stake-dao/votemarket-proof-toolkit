import json
import os
from pathlib import Path

from rich import print
from solcx import compile_source, install_solc

# Install specific solc version
install_solc("0.8.19")


def compile_contract(source_path: str) -> dict:
    """
    Compile a single Solidity contract.
    """
    with open(source_path, "r") as f:
        source = f.read()

    compiled = compile_source(
        source, output_values=["abi", "bin"], solc_version="0.8.19"
    )

    # Get the first contract from compilation output
    # This handles cases where filename != contract name
    contract_id = list(compiled.keys())[0]
    return compiled[contract_id]


def save_bytecode(bytecode: str, contract_name: str, output_dir: str):
    """
    Save bytecode to a JSON file.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{contract_name}.json")

    with open(output_path, "w") as f:
        json.dump(
            {"bytecode": bytecode, "contract_name": contract_name}, f, indent=2
        )


def main():
    # Define directories
    contracts_dir = Path("contracts/")
    bytecode_dir = Path("bytecodes/")

    # Create output directory if it doesn't exist
    os.makedirs(bytecode_dir, exist_ok=True)

    # Compile all .sol files
    for contract_file in contracts_dir.glob("*.sol"):
        print(f"Compiling {contract_file.name}...")

        try:
            # Compile contract
            compiled = compile_contract(str(contract_file))

            # Save bytecode
            save_bytecode(
                bytecode=compiled["bin"],
                contract_name=contract_file.stem,
                output_dir=str(bytecode_dir),
            )
            print(f"✓ Successfully compiled {contract_file.name}")

        except Exception as e:
            print(f"✗ Failed to compile {contract_file.name}: {str(e)}")


if __name__ == "__main__":
    main()
