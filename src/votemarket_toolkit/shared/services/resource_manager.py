import json
import os
from pathlib import Path
from typing import Any, Dict


class ResourceManager:
    """Manages access to project resources like ABIs, bytecodes, and contracts"""

    def __init__(self):
        self._package_root = Path(__file__).parent.parent.parent
        self._cache: Dict[str, Any] = {}

    def get_resource_path(self, resource_type: str, filename: str) -> Path:
        """Get full path to a resource file"""
        resource_dir = self._package_root / "resources" / resource_type
        return resource_dir / filename

    def ensure_resource_dir(self, resource_type: str) -> Path:
        """Ensure resource directory exists and return its path"""
        resource_dir = self._package_root / "resources" / resource_type
        os.makedirs(resource_dir, exist_ok=True)
        return resource_dir

    def load_abi(self, name: str) -> Dict:
        """Load an ABI file from the resources"""
        cache_key = f"abi:{name}"
        if cache_key not in self._cache:
            abi_path = self.get_resource_path("abi", f"{name}.json")
            if not abi_path.exists():
                raise FileNotFoundError(f"ABI file not found: {abi_path}")
            with open(abi_path) as f:
                self._cache[cache_key] = json.load(f)
        return self._cache[cache_key]

    def load_bytecode(self, name: str) -> Dict:
        """Load a bytecode file from the resources"""
        cache_key = f"bytecode:{name}"
        if cache_key not in self._cache:
            bytecode_path = self.get_resource_path("bytecodes", f"{name}.json")
            if not bytecode_path.exists():
                raise FileNotFoundError(
                    f"Bytecode file not found: {bytecode_path}"
                )
            with open(bytecode_path) as f:
                self._cache[cache_key] = json.load(f)
        return self._cache[cache_key]

    def save_bytecode(self, bytecode: str, contract_name: str):
        """Save bytecode to the resources directory"""
        bytecode_dir = self.ensure_resource_dir("bytecodes")
        output_path = bytecode_dir / f"{contract_name}.json"

        with open(output_path, "w") as f:
            json.dump(
                {"bytecode": bytecode, "contract_name": contract_name},
                f,
                indent=2,
            )


# Global instance
resource_manager = ResourceManager()
