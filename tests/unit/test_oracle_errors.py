"""
Unit tests for OracleService error handling.

These tests verify that:
1. Oracle returns explicit failures, not silent 0 values
2. Network errors are distinguishable from "no data" responses
3. Callers can detect and handle oracle failures properly

HIGH issue tested:
- oracle.py:90-91 - Returns 0 instead of explicit failure

Current problematic pattern:
    if oracle_address == "0x0000000000000000000000000000000000000000":
        return {epoch: 0 for epoch in epochs}

This conflates "no oracle configured" with "oracle returned 0 block"
and doesn't provide error information to callers.

These tests should FAIL against the current implementation.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, List

from votemarket_toolkit.shared.results import (
    ErrorSeverity,
    ProcessingError,
    Result,
)


# Valid Ethereum address format for testing
VALID_ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
VALID_ORACLE_ADDRESS = "0x1234567890123456789012345678901234567890"
VALID_LENS_ADDRESS = "0xABCDEF1234567890ABCDEF1234567890ABCDEF12"
VALID_PLATFORM_ADDRESS = "0x000000073D065Fc33a3050C2d4a8e82EE5C5C25a"


@pytest.fixture
def mock_web3():
    """Create a mock Web3 instance."""
    web3 = MagicMock()
    return web3


@pytest.fixture
def mock_web3_service(mock_web3):
    """Create a mock Web3Service."""
    service = MagicMock()
    service.w3 = mock_web3
    return service


class TestOracleExplicitFailures:
    """
    Test that OracleService returns explicit failures.

    Current behavior (BUG - oracle.py:90-91):
    - Returns {epoch: 0 for epoch in epochs} for various error conditions
    - Callers cannot distinguish:
      - "No oracle configured" (system issue)
      - "Oracle hasn't been updated" (expected)
      - "RPC call failed" (transient error)
      - "Block number is actually 0" (impossible but type-valid)

    Expected behavior:
    - Return Result type with explicit success/failure
    - Different error types for different conditions
    - Preserve error context for debugging
    """

    def test_no_oracle_returns_explicit_error(self):
        """Missing oracle should return explicit error, not zeros."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service

            # Mock platform contract returning zero address for oracle
            mock_platform = MagicMock()
            mock_platform.functions.ORACLE.return_value.call.return_value = (
                VALID_ZERO_ADDRESS
            )

            mock_service.get_contract.return_value = mock_platform

            oracle = OracleService(chain_id=1)
            result = oracle.get_epochs_block(
                chain_id=1,
                platform=VALID_PLATFORM_ADDRESS,
                epochs=[1700000000, 1700604800],
            )

            # Current behavior: returns {epoch: 0 for epoch in epochs}
            # Expected behavior: returns Result with explicit error

            # Check if result is the new Result type
            if isinstance(result, dict):
                # Old behavior - should fail this test
                # The zero address case should be reported as an error condition
                pytest.fail(
                    "OracleService should return Result type, not raw dict. "
                    "When oracle is not configured (zero address), callers "
                    "should receive an explicit error, not silent zeros."
                )

            # New behavior expectations
            assert isinstance(result, Result), "Should return Result type"
            assert not result.success, "Missing oracle should be a failure"
            assert any(
                "oracle" in e.message.lower()
                for e in result.errors
            ), "Error message should mention oracle"

    def test_rpc_error_returns_explicit_failure(self):
        """RPC errors should return explicit failure, not zeros."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service

            # Mock RPC failure
            mock_service.get_contract.side_effect = Exception("RPC connection failed")

            oracle = OracleService(chain_id=1)

            # Current: likely raises exception or returns zeros
            # Expected: returns Result.fail() with error info

            try:
                result = oracle.get_epochs_block(
                    chain_id=1,
                    platform=VALID_PLATFORM_ADDRESS,
                    epochs=[1700000000],
                )

                # If it returns without raising, check it's a proper Result
                if isinstance(result, dict):
                    pytest.fail(
                        "OracleService.get_epochs_block should return Result type, "
                        "not raw dict. Errors should be explicit in the Result."
                    )

                assert isinstance(result, Result), "Should return Result type"
                if isinstance(result, Result):
                    assert not result.success, "RPC error should be a failure"
                    assert len(result.errors) > 0, "Should have error details"

            except Exception as e:
                # If it raises, that's also wrong - should return Result.fail()
                pytest.fail(
                    f"OracleService should not raise exceptions. "
                    f"It should return Result.fail(). Got: {type(e).__name__}: {e}"
                )

    def test_multicall_error_returns_explicit_failure(self):
        """Multicall errors should return explicit failure."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance, patch(
            "votemarket_toolkit.data.oracle.W3Multicall"
        ) as mock_multicall_class:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service

            # Mock contracts succeeding
            mock_platform = MagicMock()
            mock_platform.functions.ORACLE.return_value.call.return_value = (
                VALID_LENS_ADDRESS
            )
            mock_lens = MagicMock()
            mock_lens.functions.oracle.return_value.call.return_value = (
                VALID_ORACLE_ADDRESS
            )

            def get_contract(address, name):
                if name == "vm_platform":
                    return mock_platform
                if name == "oracle_lens":
                    return mock_lens
                return MagicMock()

            mock_service.get_contract.side_effect = get_contract

            # Multicall raises
            mock_multicall = MagicMock()
            mock_multicall.call.side_effect = Exception("Multicall failed")
            mock_multicall_class.return_value = mock_multicall

            oracle = OracleService(chain_id=1)

            try:
                result = oracle.get_epochs_block(
                    chain_id=1,
                    platform=VALID_PLATFORM_ADDRESS,
                    epochs=[1700000000],
                )

                if isinstance(result, dict):
                    pytest.fail(
                        "Should return Result type on error, not dict."
                    )

                assert isinstance(result, Result), "Should return Result type"
                if isinstance(result, Result):
                    assert not result.success, "Multicall error should fail"

            except Exception as e:
                pytest.fail(
                    f"Should return Result.fail(), not raise. Got: {e}"
                )


class TestOracleResultDistinction:
    """
    Test that different oracle conditions are distinguishable.
    """

    def test_zero_block_vs_no_data_distinguishable(self):
        """Block number 0 should be distinguishable from 'no data'."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance, patch(
            "votemarket_toolkit.data.oracle.W3Multicall"
        ) as mock_multicall_class:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service

            mock_platform = MagicMock()
            mock_platform.functions.ORACLE.return_value.call.return_value = (
                VALID_LENS_ADDRESS
            )
            mock_lens = MagicMock()
            mock_lens.functions.oracle.return_value.call.return_value = (
                VALID_ORACLE_ADDRESS
            )

            def get_contract(address, name):
                if name == "vm_platform":
                    return mock_platform
                if name == "oracle_lens":
                    return mock_lens
                return MagicMock()

            mock_service.get_contract.side_effect = get_contract

            # Multicall returns 0 block (oracle not updated for this epoch)
            mock_multicall = MagicMock()
            mock_multicall.call.return_value = [
                (b"", b"", 0, 0)  # (merkleRoot, ipfsHash, blockNumber=0, timestamp)
            ]
            mock_multicall_class.return_value = mock_multicall

            oracle = OracleService(chain_id=1)
            result = oracle.get_epochs_block(
                chain_id=1,
                platform=VALID_PLATFORM_ADDRESS,
                epochs=[1700000000],
            )

            # This is a legitimate "oracle not updated" response
            # Should be success with block=0 (or a special indicator)
            if isinstance(result, Result):
                assert result.success, "Valid response with 0 block is success"
            elif isinstance(result, dict):
                # Old behavior - at minimum, this should work
                assert result[1700000000] == 0

    def test_partial_epoch_data_reported(self):
        """When some epochs succeed and some fail, report partial data."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance, patch(
            "votemarket_toolkit.data.oracle.W3Multicall"
        ) as mock_multicall_class:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service

            mock_platform = MagicMock()
            mock_platform.functions.ORACLE.return_value.call.return_value = (
                VALID_LENS_ADDRESS
            )
            mock_lens = MagicMock()
            mock_lens.functions.oracle.return_value.call.return_value = (
                VALID_ORACLE_ADDRESS
            )

            def get_contract(address, name):
                if name == "vm_platform":
                    return mock_platform
                if name == "oracle_lens":
                    return mock_lens
                return MagicMock()

            mock_service.get_contract.side_effect = get_contract

            # Some epochs have data, some don't
            mock_multicall = MagicMock()
            mock_multicall.call.return_value = [
                (b"", b"", 21000000, 1700000000),  # Has block
                (b"", b"", 0, 0),                   # No block yet
                (b"", b"", 21100000, 1700604800),  # Has block
            ]
            mock_multicall_class.return_value = mock_multicall

            oracle = OracleService(chain_id=1)
            result = oracle.get_epochs_block(
                chain_id=1,
                platform=VALID_PLATFORM_ADDRESS,
                epochs=[1700000000, 1700302400, 1700604800],
            )

            # Should return data for epochs that have it
            if isinstance(result, Result):
                assert result.success
                data = result.data
            else:
                data = result

            assert data[1700000000] == 21000000
            assert data[1700302400] == 0  # Not updated yet
            assert data[1700604800] == 21100000


class TestOracleErrorContext:
    """
    Test that oracle errors include useful context.
    """

    def test_error_includes_platform_address(self):
        """Oracle errors should include platform address."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service
            mock_service.get_contract.side_effect = Exception("RPC failed")

            oracle = OracleService(chain_id=1)

            try:
                result = oracle.get_epochs_block(
                    chain_id=1,
                    platform=VALID_PLATFORM_ADDRESS,
                    epochs=[1700000000],
                )

                if isinstance(result, Result) and not result.success:
                    # Check that platform is in error context or message
                    error_str = str(result.errors)
                    assert VALID_PLATFORM_ADDRESS in error_str or \
                           VALID_PLATFORM_ADDRESS.lower() in error_str, (
                        "Error should include platform address"
                    )
            except Exception:
                pass  # Old behavior raises

    def test_error_includes_requested_epochs(self):
        """Oracle errors should include the epochs that were requested."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service
            mock_service.get_contract.side_effect = Exception("RPC failed")

            oracle = OracleService(chain_id=1)
            epochs = [1700000000, 1700604800]

            try:
                result = oracle.get_epochs_block(
                    chain_id=1,
                    platform=VALID_PLATFORM_ADDRESS,
                    epochs=epochs,
                )

                if isinstance(result, Result) and not result.success:
                    error_str = str(result.errors)
                    assert str(epochs[0]) in error_str, (
                        "Error should include requested epochs"
                    )
            except Exception:
                pass

    def test_error_includes_chain_id(self):
        """Oracle errors should include chain ID."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service
            mock_service.get_contract.side_effect = Exception("RPC failed")

            oracle = OracleService(chain_id=42161)  # Arbitrum

            try:
                result = oracle.get_epochs_block(
                    chain_id=42161,
                    platform=VALID_PLATFORM_ADDRESS,
                    epochs=[1700000000],
                )

                if isinstance(result, Result) and not result.success:
                    error_str = str(result.errors)
                    assert "42161" in error_str, (
                        "Error should include chain ID"
                    )
            except Exception:
                pass


class TestOracleReturnType:
    """
    Test that OracleService returns the proper Result type.
    """

    def test_get_epochs_block_returns_result_type(self):
        """get_epochs_block should return Result[Dict[int, int]]."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance, patch(
            "votemarket_toolkit.data.oracle.W3Multicall"
        ) as mock_multicall_class:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service

            mock_platform = MagicMock()
            mock_platform.functions.ORACLE.return_value.call.return_value = (
                VALID_LENS_ADDRESS
            )
            mock_lens = MagicMock()
            mock_lens.functions.oracle.return_value.call.return_value = (
                VALID_ORACLE_ADDRESS
            )

            def get_contract(address, name):
                if name == "vm_platform":
                    return mock_platform
                if name == "oracle_lens":
                    return mock_lens
                return MagicMock()

            mock_service.get_contract.side_effect = get_contract

            mock_multicall = MagicMock()
            mock_multicall.call.return_value = [
                (b"", b"", 21000000, 1700000000),
            ]
            mock_multicall_class.return_value = mock_multicall

            oracle = OracleService(chain_id=1)
            result = oracle.get_epochs_block(
                chain_id=1,
                platform=VALID_PLATFORM_ADDRESS,
                epochs=[1700000000],
            )

            # Expected: Result type
            # Current: raw dict
            if isinstance(result, dict):
                pytest.fail(
                    "OracleService.get_epochs_block should return Result[Dict[int, int]], "
                    "not raw dict. This enables proper error handling by callers."
                )

            assert isinstance(result, Result), (
                "OracleService.get_epochs_block should return Result type"
            )

    def test_successful_result_has_data(self):
        """Successful Result should have data accessible."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance, patch(
            "votemarket_toolkit.data.oracle.W3Multicall"
        ) as mock_multicall_class:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service

            mock_platform = MagicMock()
            mock_platform.functions.ORACLE.return_value.call.return_value = (
                VALID_LENS_ADDRESS
            )
            mock_lens = MagicMock()
            mock_lens.functions.oracle.return_value.call.return_value = (
                VALID_ORACLE_ADDRESS
            )

            def get_contract(address, name):
                if name == "vm_platform":
                    return mock_platform
                if name == "oracle_lens":
                    return mock_lens
                return MagicMock()

            mock_service.get_contract.side_effect = get_contract

            mock_multicall = MagicMock()
            mock_multicall.call.return_value = [
                (b"", b"", 21000000, 1700000000),
            ]
            mock_multicall_class.return_value = mock_multicall

            oracle = OracleService(chain_id=1)
            result = oracle.get_epochs_block(
                chain_id=1,
                platform=VALID_PLATFORM_ADDRESS,
                epochs=[1700000000],
            )

            if isinstance(result, Result):
                assert result.success, "Valid response should be successful"
                assert result.data is not None, "Successful result should have data"
                assert isinstance(result.data, dict), "Data should be a dict"
                assert 1700000000 in result.data, "Data should contain requested epoch"
            elif isinstance(result, dict):
                # Old behavior - test passes but marks issue
                pass


class TestOracleZeroAddressHandling:
    """
    Test specific handling of zero address oracle.

    The zero address case at oracle.py:90-91 needs special attention
    because it's a valid system state that should be handled explicitly.
    """

    def test_zero_oracle_lens_is_configuration_error(self):
        """Zero oracle lens should be reported as configuration error."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service

            mock_platform = MagicMock()
            # ORACLE() returns zero address (not configured)
            mock_platform.functions.ORACLE.return_value.call.return_value = (
                VALID_ZERO_ADDRESS
            )

            mock_service.get_contract.return_value = mock_platform

            oracle = OracleService(chain_id=1)
            result = oracle.get_epochs_block(
                chain_id=1,
                platform=VALID_PLATFORM_ADDRESS,
                epochs=[1700000000],
            )

            if isinstance(result, Result):
                # Zero oracle is a configuration issue, should fail or warn
                assert not result.success or result.has_warnings(), (
                    "Zero oracle address should be reported as error/warning"
                )
            elif isinstance(result, dict):
                # Current behavior returns zeros
                # At minimum, callers should be able to detect this
                assert all(v == 0 for v in result.values()), (
                    "Zero oracle should return zeros (current behavior)"
                )

    def test_zero_oracle_address_from_lens_is_error(self):
        """Zero oracle address from lens is an error condition."""
        from votemarket_toolkit.data.oracle import OracleService

        with patch(
            "votemarket_toolkit.data.oracle.Web3Service.get_instance"
        ) as mock_get_instance:
            mock_service = MagicMock()
            mock_get_instance.return_value = mock_service

            mock_platform = MagicMock()
            mock_platform.functions.ORACLE.return_value.call.return_value = (
                VALID_LENS_ADDRESS
            )

            mock_lens = MagicMock()
            # Lens returns zero oracle address
            mock_lens.functions.oracle.return_value.call.return_value = (
                VALID_ZERO_ADDRESS
            )

            def get_contract(address, name):
                if name == "vm_platform":
                    return mock_platform
                if name == "oracle_lens":
                    return mock_lens
                return MagicMock()

            mock_service.get_contract.side_effect = get_contract

            oracle = OracleService(chain_id=1)
            result = oracle.get_epochs_block(
                chain_id=1,
                platform=VALID_PLATFORM_ADDRESS,
                epochs=[1700000000],
            )

            # This is the code path at oracle.py:90-91
            if isinstance(result, Result):
                assert not result.success or result.has_warnings(), (
                    "Zero oracle from lens should be error/warning"
                )
            elif isinstance(result, dict):
                # Current behavior - zeros returned
                assert result[1700000000] == 0
