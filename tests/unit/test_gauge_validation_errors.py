"""
Unit tests for gauge validation error handling (fail-closed behavior).

These tests verify that:
1. RPC errors do NOT result in "assume valid" behavior
2. Validation failures are explicit, not silent assumptions
3. The fail-closed principle is enforced

CRITICAL issue tested:
- manager.py:280-295 - Pendle assumes gauge valid on RPC error

The current code has this dangerous pattern:
    except Exception as e:
        # If getAllActivePools() fails, assume valid with warning
        result = Result.ok(
            GaugeValidationResult(
                is_valid=True,  # <-- DANGEROUS: assumes valid on error
                reason=f"getAllActivePools() failed, assuming valid: {str(e)}",
                ...
            )
        )

This violates the fail-closed principle and could lead to:
- Processing invalid gauges
- Generating proofs for non-existent pools
- Wasted resources and incorrect data

These tests should FAIL against the current implementation.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from web3.exceptions import ContractLogicError

from votemarket_toolkit.proofs.manager import (
    VoteMarketProofs,
    GaugeValidationResult,
)
from votemarket_toolkit.shared.results import (
    ErrorSeverity,
    ProcessingError,
    Result,
)


@pytest.fixture
def mock_web3_service():
    """Create a mock Web3Service."""
    service = MagicMock()
    service.w3 = MagicMock()
    return service


@pytest.fixture
def proof_manager():
    """Create a VoteMarketProofs instance with mocked dependencies."""
    with patch(
        "votemarket_toolkit.proofs.manager.GlobalConstants.get_rpc_url"
    ) as mock_rpc:
        mock_rpc.return_value = "http://localhost:8545"
        with patch(
            "votemarket_toolkit.proofs.manager.Web3Service"
        ) as mock_ws_class:
            mock_ws = MagicMock()
            mock_ws_class.return_value = mock_ws
            manager = VoteMarketProofs(chain_id=1)
            manager.web3_service = mock_ws
            return manager


class TestPendleGaugeValidationFailClosed:
    """
    Test that Pendle gauge validation follows fail-closed principle.

    Current behavior (BUG - manager.py:280-295):
    - When getAllActivePools() RPC call fails, code assumes gauge is valid
    - This is "fail-open" behavior which is dangerous

    Expected behavior (fail-closed):
    - When RPC fails, validation should FAIL (gauge not validated)
    - Caller should know validation could not be performed
    - No assumptions about validity on error
    """

    def test_pendle_rpc_error_does_not_assume_valid(self, proof_manager):
        """
        RPC error should NOT result in is_valid=True.

        This is the critical test. The current code at manager.py:280-295 does:
            except Exception as e:
                result = Result.ok(GaugeValidationResult(is_valid=True, ...))

        This is wrong. It should fail-closed:
            except Exception as e:
                return Result.fail(...)
        """
        # Mock the contract to raise an exception
        mock_contract = MagicMock()
        mock_contract.functions.getAllActivePools.return_value.call.side_effect = (
            Exception("RPC connection failed")
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234567890123456789012345678901234567890"

            result = proof_manager.is_valid_gauge(
                protocol="pendle",
                gauge="0xABCDEF1234567890ABCDEF1234567890ABCDEF12",
            )

            # CURRENT BEHAVIOR (BUG): Returns success with is_valid=True
            # EXPECTED BEHAVIOR: Returns failure OR is_valid=False

            if result.success and result.data:
                assert result.data.is_valid is False, (
                    "FAIL-CLOSED VIOLATION: RPC error should NOT result in is_valid=True. "
                    "Current code at manager.py:280-295 assumes gauge is valid on RPC failure. "
                    "This is dangerous - an invalid gauge could be processed."
                )
            else:
                # If result.success is False, that's acceptable fail-closed behavior
                assert not result.success, "RPC failure should return Result.fail()"

    def test_pendle_rpc_timeout_fails_validation(self, proof_manager):
        """RPC timeout should fail validation, not assume valid."""
        mock_contract = MagicMock()
        mock_contract.functions.getAllActivePools.return_value.call.side_effect = (
            TimeoutError("Request timed out after 30s")
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="pendle",
                gauge="0xABCD",
            )

            # Fail-closed: timeout means we couldn't validate
            if result.success and result.data:
                assert result.data.is_valid is False, (
                    "Timeout should NOT result in is_valid=True"
                )

    def test_pendle_contract_revert_fails_validation(self, proof_manager):
        """Contract revert should fail validation."""
        mock_contract = MagicMock()
        mock_contract.functions.getAllActivePools.return_value.call.side_effect = (
            ContractLogicError("execution reverted")
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="pendle",
                gauge="0xABCD",
            )

            if result.success and result.data:
                assert result.data.is_valid is False, (
                    "Contract revert should NOT result in is_valid=True"
                )

    def test_pendle_rpc_error_returns_result_fail(self, proof_manager):
        """
        RPC error should return Result.fail(), not Result.ok() with warning.

        The proper fail-closed pattern is to return Result.fail() so
        the caller knows validation could not be completed.
        """
        mock_contract = MagicMock()
        mock_contract.functions.getAllActivePools.return_value.call.side_effect = (
            ConnectionError("Network unreachable")
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="pendle",
                gauge="0xABCD",
            )

            # Preferred behavior: Result.fail() on RPC error
            # Acceptable alternative: Result.ok() with is_valid=False
            if result.success:
                assert result.data.is_valid is False, (
                    "RPC error must not assume valid. Either return Result.fail() "
                    "or Result.ok(GaugeValidationResult(is_valid=False))"
                )
                assert "error" in result.data.reason.lower() or "failed" in result.data.reason.lower(), (
                    "Reason should indicate validation failed due to error"
                )

    def test_pendle_error_includes_context_for_debugging(self, proof_manager):
        """Validation errors should include context for debugging."""
        mock_contract = MagicMock()
        mock_contract.functions.getAllActivePools.return_value.call.side_effect = (
            Exception("Some RPC error")
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract

        gauge = "0xABCDEF1234567890ABCDEF1234567890ABCDEF12"

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="pendle",
                gauge=gauge,
            )

            # Error context should include gauge and protocol
            if result.errors:
                context = result.errors[0].context
                assert "gauge" in context or gauge in str(result.errors[0]), (
                    "Error should include gauge address for debugging"
                )
                assert "pendle" in str(result).lower(), (
                    "Error should include protocol for debugging"
                )


class TestYBGaugeValidationFailClosed:
    """
    Test YB (Yearn Boost) gauge validation error handling.
    """

    def test_yb_rpc_error_does_not_assume_valid(self, proof_manager):
        """YB gauge validation should fail-closed on RPC error."""
        mock_contract = MagicMock()
        mock_contract.functions.n_gauges.return_value.call.side_effect = (
            Exception("RPC failed")
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract
        proof_manager.yb_gauges = None  # Force re-fetch

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="yb",
                gauge="0xABCD",
            )

            # Should not assume valid on error
            if result.success and result.data:
                assert result.data.is_valid is False, (
                    "YB RPC error should not assume valid"
                )


class TestGenericGaugeValidationFailClosed:
    """
    Test generic (Curve-style) gauge validation error handling.
    """

    def test_gauge_types_revert_indicates_invalid(self, proof_manager):
        """gauge_types() revert means gauge is invalid, not an error."""
        mock_contract = MagicMock()
        # gauge_types reverts for invalid gauges
        mock_contract.functions.gauge_types.return_value.call.side_effect = (
            ContractLogicError("execution reverted")
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="curve",
                gauge="0xINVALID",
            )

            # Revert means gauge not in controller = invalid
            if result.success and result.data:
                assert result.data.is_valid is False, (
                    "gauge_types() revert means gauge is invalid"
                )

    def test_rpc_error_different_from_contract_revert(self, proof_manager):
        """RPC errors should be distinguishable from contract reverts."""
        # Contract revert = gauge invalid (determinate)
        # RPC error = couldn't check (indeterminate, should fail-closed)

        mock_contract = MagicMock()
        mock_contract.functions.gauge_types.return_value.call.side_effect = (
            ConnectionError("Network error")
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="curve",
                gauge="0xABCD",
            )

            # Network error = couldn't validate = should fail
            assert not result.success or result.data.is_valid is False, (
                "Network error should result in validation failure"
            )


class TestGaugeValidationRetryBehavior:
    """
    Test that gauge validation retries appropriately.
    """

    def test_validation_retries_on_transient_error(self, proof_manager):
        """Validation should retry on transient errors before failing."""
        call_count = 0

        def flaky_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("Temporary timeout")
            return ["0xABCD"]  # Success on 3rd try

        mock_contract = MagicMock()
        mock_contract.functions.getAllActivePools.return_value.call.side_effect = (
            flaky_call
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="pendle",
                gauge="0xABCD",
                max_retries=3,
            )

            # Should succeed after retries
            assert result.success, "Should succeed after transient errors resolve"
            assert result.data.is_valid is True

    def test_validation_fails_after_max_retries(self, proof_manager):
        """Validation should fail-closed after exhausting retries."""
        mock_contract = MagicMock()
        mock_contract.functions.getAllActivePools.return_value.call.side_effect = (
            Exception("Persistent failure")
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="pendle",
                gauge="0xABCD",
                max_retries=3,
            )

            # After all retries fail, should fail-closed
            if result.success and result.data:
                assert result.data.is_valid is False, (
                    "Exhausted retries should fail-closed, not assume valid"
                )


class TestGaugeValidationResultDetails:
    """
    Test GaugeValidationResult contains useful information.
    """

    def test_valid_gauge_includes_reason(self, proof_manager):
        """Valid gauge result should include reason for validity."""
        mock_contract = MagicMock()
        mock_contract.functions.getAllActivePools.return_value.call.return_value = [
            "0xABCD1234567890ABCD1234567890ABCD12345678"
        ]
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="pendle",
                gauge="0xABCD1234567890ABCD1234567890ABCD12345678",
            )

            assert result.success
            assert result.data.is_valid is True
            assert result.data.reason is not None
            assert len(result.data.reason) > 0

    def test_invalid_gauge_includes_reason(self, proof_manager):
        """Invalid gauge result should include reason for invalidity."""
        mock_contract = MagicMock()
        mock_contract.functions.getAllActivePools.return_value.call.return_value = [
            "0x1111111111111111111111111111111111111111"
        ]
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="pendle",
                gauge="0x2222222222222222222222222222222222222222",  # Not in list
            )

            assert result.success
            assert result.data.is_valid is False
            assert "not found" in result.data.reason.lower()

    def test_error_result_includes_exception_info(self, proof_manager):
        """Error result should include original exception information."""
        original_error = ConnectionError("Specific network error details")
        mock_contract = MagicMock()
        mock_contract.functions.getAllActivePools.return_value.call.side_effect = (
            original_error
        )
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            result = proof_manager.is_valid_gauge(
                protocol="pendle",
                gauge="0xABCD",
            )

            # If it fails (correct behavior), exception should be preserved
            if not result.success:
                assert result.errors[0].exception is not None
                assert "network" in str(result.errors[0].exception).lower()


class TestFailClosedPrinciple:
    """
    Meta-tests verifying the fail-closed principle is consistently applied.
    """

    def test_no_is_valid_true_on_any_exception(self, proof_manager):
        """
        No exception should ever result in is_valid=True.

        This is the fundamental fail-closed principle:
        If we can't verify, we don't assume validity.
        """
        exception_types = [
            Exception("Generic"),
            ConnectionError("Network"),
            TimeoutError("Timeout"),
            RuntimeError("Runtime"),
            OSError("OS level"),
        ]

        mock_contract = MagicMock()
        proof_manager.web3_service.get_contract.return_value = mock_contract

        with patch(
            "votemarket_toolkit.proofs.manager.registry.get_gauge_controller"
        ) as mock_registry:
            mock_registry.return_value = "0x1234"

            for exc in exception_types:
                mock_contract.functions.getAllActivePools.return_value.call.side_effect = exc

                result = proof_manager.is_valid_gauge(
                    protocol="pendle",
                    gauge="0xABCD",
                    max_retries=1,  # Fast fail for test
                )

                if result.success and result.data:
                    assert result.data.is_valid is False, (
                        f"Exception {type(exc).__name__} should NOT result in is_valid=True. "
                        f"This violates the fail-closed principle."
                    )
