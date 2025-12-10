"""
Pytest configuration and shared fixtures.

This module provides common fixtures and configuration for all tests.
"""

import asyncio
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_web3_service():
    """Mock Web3Service for unit tests."""
    service = MagicMock()
    service.w3 = MagicMock()
    service.w3.eth.get_proof.return_value = {
        "accountProof": ["0x1234"],
        "storageProof": [{"proof": ["0x5678"]}],
    }
    service.w3.eth.get_block.return_value = {
        "number": 21000000,
        "hash": "0x" + "ef" * 32,
        "timestamp": 1764806400,
    }
    return service


@pytest.fixture
def mock_rpc_responses() -> Dict[str, Any]:
    """Common RPC response mocks."""
    return {
        "get_proof": {
            "accountProof": ["0x" + "ab" * 32],
            "storageProof": [{"proof": ["0x" + "cd" * 32]}],
        },
        "get_block": {
            "number": 21000000,
            "hash": "0x" + "ef" * 32,
            "timestamp": 1764806400,
        },
    }


@pytest.fixture
def sample_gauge_address() -> str:
    """Sample gauge address for tests."""
    return "0x7E1444BA99dcdFfE8fBdb42C02fb0DA4AAAcE4d5"


@pytest.fixture
def sample_user_address() -> str:
    """Sample user address for tests."""
    return "0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6"


@pytest.fixture
def sample_platform_address() -> str:
    """Sample platform address for tests."""
    return "0x000000073D065Fc33a3050C2d4a8e82EE5C5C25a"


@pytest.fixture
def sample_epoch() -> int:
    """Sample epoch timestamp for tests."""
    return 1764806400


@pytest.fixture
def sample_block_number() -> int:
    """Sample block number for tests."""
    return 21000000


@pytest.fixture
def sample_platforms_data() -> Dict[str, Any]:
    """Sample all_platforms.json structure for tests."""
    return {
        "protocols": {
            "curve": {
                "platforms": {
                    "1": [
                        {
                            "address": "0x000000073D065Fc33a3050C2d4a8e82EE5C5C25a",
                            "latest_setted_block": 21000000,
                            "block_data": {
                                "block_number": 21000000,
                                "block_hash": "0x" + "ab" * 32,
                                "block_timestamp": 1764806400,
                            },
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def sample_campaign() -> Dict[str, Any]:
    """Sample campaign data for tests."""
    return {
        "id": 0,
        "campaign": {
            "gauge": "0x7E1444BA99dcdFfE8fBdb42C02fb0DA4AAAcE4d5",
            "manager": "0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6",
            "reward_token": "0xD533a949740bb3306d119CC777fa900bA034cd52",
            "number_of_periods": 4,
            "max_reward_per_vote": 1000000000000000000,
            "total_reward_amount": 100000000000000000000,
            "total_distributed": 25000000000000000000,
            "start_timestamp": 1764201600,
            "end_timestamp": 1766620800,
            "hook": "0x0000000000000000000000000000000000000000",
        },
        "remaining_periods": 3,
        "is_closed": False,
        "addresses": [],
        "periods": [
            {
                "timestamp": 1764201600,
                "reward_per_period": 25000000000000000000,
                "reward_per_vote": 1000000000,
                "leftover": 0,
                "updated": True,
            }
        ],
    }


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line("markers", "slow: mark test as slow-running")
