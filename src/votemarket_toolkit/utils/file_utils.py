import json
from typing import Any, Dict


def load_json(file_path: str) -> Dict[str, Any]:
    """Load and parse a JSON file"""
    with open(file_path, "r") as file:
        return json.load(file)
