"""
Unit tests for CampaignService error handling paths.

These tests verify that:
1. Bare excepts do NOT swallow errors silently
2. Errors are logged with proper context
3. Callers can detect when errors occurred
4. Partial data is returned with error information

CRITICAL issues tested:
- service.py:382-384 - Bare except swallows proof enrichment errors
- service.py:379-381 - Nested bare except skips campaign proof flags

HIGH issues tested:
- service.py:713-720 - Returns [] with only debug log
- service.py:808-815 - Returns None filtered out silently

These tests should FAIL against the current implementation.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import List, Dict, Any

from votemarket_toolkit.shared.results import (
    ErrorSeverity,
    ProcessingError,
    Result,
)


@pytest.fixture
def mock_web3():
    """Create a mock Web3 instance."""
    web3 = MagicMock()
    web3.eth.get_block.return_value = {
        "number": 21000000,
        "hash": "0x" + "ab" * 32,
        "timestamp": 1700000000,
    }
    return web3


@pytest.fixture
def mock_web3_service(mock_web3):
    """Create a mock Web3Service."""
    service = MagicMock()
    service.w3 = mock_web3
    service.get_contract.return_value = MagicMock()
    return service


@pytest.fixture
def mock_contract_reader():
    """Create a mock ContractReader."""
    reader = MagicMock()
    reader.decode_campaign_batch.return_value = [
        {
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
    ]
    reader.decode_active_campaign_ids.return_value = {"campaign_ids": [0, 1, 2]}
    return reader


class TestProofEnrichmentErrorHandling:
    """
    Test that proof enrichment errors are NOT silently swallowed.

    Current behavior (BUG):
    - service.py:382-384 has bare `except Exception: return`
    - This silently swallows ALL errors during proof enrichment
    - Callers have no way to know enrichment failed

    Expected behavior (after fix):
    - Errors are captured in Result
    - Callers can detect partial enrichment
    - Error context is preserved for debugging
    """

    @pytest.mark.asyncio
    async def test_proof_enrichment_error_is_reported_not_swallowed(self):
        """Proof enrichment errors should be reported, not silently swallowed."""
        from votemarket_toolkit.campaigns.service import CampaignService

        service = CampaignService()

        # Mock the proof status population to raise an exception
        with patch.object(
            service, "_populate_proof_status_flags"
        ) as mock_populate:
            mock_populate.side_effect = Exception("Oracle RPC failed")

            # Also need to mock the actual campaign fetch to return data
            with patch.object(
                service, "_fetch_campaigns_by_ids"
            ) as mock_fetch, patch(
                "votemarket_toolkit.shared.services.web3_service.Web3Service.get_instance"
            ) as mock_ws:
                mock_ws.return_value = MagicMock()
                mock_fetch.return_value = [
                    {
                        "id": 0,
                        "campaign": {
                            "gauge": "0x7E1444BA99dcdFfE8fBdb42C02fb0DA4AAAcE4d5",
                            "number_of_periods": 4,
                            "start_timestamp": 1764201600,
                            "end_timestamp": 1766620800,
                        },
                        "periods": [{"timestamp": 1764201600, "updated": True}],
                    }
                ]

                # The method should NOT silently swallow this error
                result = await service.get_campaigns(
                    chain_id=1,
                    platform_address="0x000000073D065Fc33a3050C2d4a8e82EE5C5C25a",
                    check_proofs=True,
                )

                # Current behavior: returns success=True, no indication of error
                # Expected behavior: returns partial_success or has warnings
                assert result.has_errors() or result.has_warnings(), (
                    "Proof enrichment errors should be reported. "
                    "Currently the bare except at service.py:382 swallows them."
                )

    @pytest.mark.asyncio
    async def test_proof_enrichment_error_preserves_campaign_data(self):
        """Even on enrichment error, campaign data should be preserved."""
        from votemarket_toolkit.campaigns.service import CampaignService

        service = CampaignService()

        campaigns_data = [
            {"id": 1, "campaign": {"gauge": "0x123"}, "periods": []},
            {"id": 2, "campaign": {"gauge": "0x456"}, "periods": []},
        ]

        # Mock successful campaign fetch but failing proof population
        with patch.object(
            service, "_fetch_campaigns_by_ids"
        ) as mock_fetch, patch.object(
            service, "_populate_proof_status_flags"
        ) as mock_populate, patch(
            "votemarket_toolkit.shared.services.web3_service.Web3Service.get_instance"
        ) as mock_ws:
            mock_ws.return_value = MagicMock()
            mock_fetch.return_value = campaigns_data
            mock_populate.side_effect = ConnectionError("Network error")

            result = await service.get_campaigns(
                chain_id=1,
                platform_address="0x000000073D065Fc33a3050C2d4a8e82EE5C5C25a",
                check_proofs=True,
            )

            # Data should still be present even if enrichment failed
            assert result.data is not None, "Campaign data should be preserved"
            assert len(result.data) == 2, "All campaigns should be returned"

            # But we should know enrichment failed
            # Check for is_partial attribute (new) or warnings (existing)
            has_partial_indicator = (
                getattr(result, "is_partial", False) or result.has_warnings()
            )
            assert has_partial_indicator, (
                "Result should indicate proof enrichment failed"
            )


class TestCampaignProofFlagsErrorHandling:
    """
    Test that campaign proof flag errors are NOT silently skipped.

    Current behavior (BUG):
    - service.py:379-381 has nested bare `except Exception: continue`
    - Individual campaign proof flag errors are silently skipped
    - No indication that some campaigns have incomplete proof data

    Expected behavior (after fix):
    - Individual failures are tracked
    - Callers know which campaigns have incomplete data
    - Error context helps debugging
    """

    @pytest.mark.asyncio
    async def test_individual_campaign_proof_flag_error_is_tracked(self):
        """Individual campaign proof flag errors should be tracked."""
        from votemarket_toolkit.campaigns.service import CampaignService

        service = CampaignService()

        campaigns = [
            {"id": 1, "periods": [{"timestamp": 1000}]},
            {"id": 2, "periods": [{"timestamp": 2000}]},
            {"id": 3, "periods": [{"timestamp": 3000}]},
        ]

        # The _populate_proof_status_flags method modifies campaigns in place
        # and has the bare except that swallows individual campaign errors.
        # We need to test that after the fix, errors are tracked.

        # Since _populate_proof_status_flags is a complex method that uses
        # OracleService internally, we test the expected behavior after fix.
        # The test verifies that the Result should contain error information.

        with patch(
            "votemarket_toolkit.campaigns.service.OracleService"
        ) as MockOracle, patch(
            "votemarket_toolkit.shared.services.web3_service.Web3Service.get_instance"
        ) as mock_ws:
            mock_ws.return_value = MagicMock()

            # Mock oracle to fail for specific epoch
            mock_oracle_instance = MagicMock()

            def mock_get_epochs(chain_id, platform, epochs):
                # Fail for campaign 2's epoch
                if 2000 in epochs:
                    raise Exception("Oracle call failed for epoch 2000")
                return {e: 21000000 for e in epochs}

            mock_oracle_instance.get_epochs_block.side_effect = mock_get_epochs
            MockOracle.return_value = mock_oracle_instance

            # Call the method under test
            await service._populate_proof_status_flags(
                chain_id=1,
                platform_address="0x123",
                campaigns=campaigns,
            )

            # After the fix, the method should return a Result with error info
            # For now, we check that the method signature changes to return Result
            # This test will fail until the fix is implemented

            # Current behavior: returns None, errors silently swallowed
            # Expected behavior: returns Result with tracked errors
            # We can't easily test this without changing the method signature,
            # so we verify via the parent method get_campaigns

        # Integration test via get_campaigns
        with patch.object(
            service, "_fetch_campaigns_by_ids"
        ) as mock_fetch, patch(
            "votemarket_toolkit.campaigns.service.OracleService"
        ) as MockOracle, patch(
            "votemarket_toolkit.shared.services.web3_service.Web3Service.get_instance"
        ) as mock_ws:
            mock_ws.return_value = MagicMock()
            mock_fetch.return_value = campaigns

            mock_oracle_instance = MagicMock()
            mock_oracle_instance.get_epochs_block.side_effect = Exception(
                "Oracle totally failed"
            )
            MockOracle.return_value = mock_oracle_instance

            result = await service.get_campaigns(
                chain_id=1,
                platform_address="0x123",
                check_proofs=True,
            )

            # The result should indicate the proof population had issues
            assert result.has_errors() or result.has_warnings(), (
                "Oracle errors during proof population should be reported. "
                "Currently the bare except at service.py:379 skips silently."
            )


class TestActiveCampaignIdsFetchErrorHandling:
    """
    Test that active campaign ID fetch errors are properly reported.

    Current behavior (BUG):
    - service.py:713-720 returns [] with only debug log
    - Callers cannot distinguish "no campaigns" from "fetch failed"
    - Silent failures lead to missing data

    Expected behavior (after fix):
    - Fetch failures return Result.fail() or partial_success
    - Error is logged at WARNING level minimum
    - Callers can detect and handle the failure
    """

    @pytest.mark.asyncio
    async def test_active_campaign_ids_fetch_error_is_distinguishable(self):
        """Fetch error should be distinguishable from empty result."""
        from votemarket_toolkit.campaigns.service import CampaignService

        service = CampaignService()

        mock_web3_service = MagicMock()
        mock_web3_service.w3.eth.call.side_effect = Exception("RPC timeout")

        # The method currently returns a raw list
        # After the fix, it should return Result
        result = await service._get_active_campaign_ids(
            web3_service=mock_web3_service,
            bytecode_data={"active_ids": "0x" + "00" * 100},
            platform_address="0x000000073D065Fc33a3050C2d4a8e82EE5C5C25a",
            total_campaigns=100,
        )

        # Current behavior: returns [], caller thinks "no active campaigns"
        # Expected behavior: returns Result.fail() or Result with error info
        if isinstance(result, list):
            # Current behavior - this test should fail
            pytest.fail(
                "Method _get_active_campaign_ids should return Result type. "
                "Currently returns raw list, which loses error information. "
                "Returning [] on error is indistinguishable from 'no active campaigns'."
            )

        # Expected new behavior
        assert isinstance(result, Result), (
            "Method should return Result type. Currently returns raw list."
        )

        if result.success and result.data == []:
            # If we got empty list, there should be an indication it was due to error
            has_error_indicator = (
                getattr(result, "is_degraded", False) or result.has_errors()
            )
            assert has_error_indicator, (
                "Empty result due to error should be distinguishable from "
                "legitimately having no active campaigns. "
                "Currently service.py:713-720 just returns []."
            )

    @pytest.mark.asyncio
    async def test_active_campaign_ids_error_logged_at_warning_level(self):
        """Fetch errors should be logged at WARNING level, not DEBUG."""
        from votemarket_toolkit.campaigns.service import CampaignService

        with patch("votemarket_toolkit.campaigns.service._logger") as mock_logger:
            service = CampaignService()

            mock_web3_service = MagicMock()
            mock_web3_service.w3.eth.call.side_effect = Exception("RPC failed")

            await service._get_active_campaign_ids(
                web3_service=mock_web3_service,
                bytecode_data={"active_ids": "0x" + "00" * 100},
                platform_address="0x000",
                total_campaigns=10,
            )

            # Current behavior: uses debug()
            # Expected behavior: uses warning() or error()
            warning_or_error_called = (
                mock_logger.warning.called or mock_logger.error.called
            )
            assert warning_or_error_called, (
                "RPC failures should be logged at WARNING level minimum. "
                "Currently service.py:713-720 uses debug level."
            )


class TestCampaignFetchErrorHandling:
    """
    Test that individual campaign fetch errors are properly reported.

    Current behavior (BUG):
    - service.py:808-815 returns None, filtered out silently
    - No indication of which campaigns failed to fetch
    - Silent data loss

    Expected behavior (after fix):
    - Failed fetches are tracked with campaign ID
    - Result indicates partial success
    - Callers know which campaigns are missing
    """

    @pytest.mark.asyncio
    async def test_campaign_fetch_failure_is_tracked(self):
        """Individual campaign fetch failures should be tracked."""
        from votemarket_toolkit.campaigns.service import CampaignService

        service = CampaignService()

        # Mock to fail for specific campaign
        original_fetch = service._fetch_single_campaign

        async def mock_fetch_single(
            web3_service, bytecode_data, platform_address, campaign_id, **kwargs
        ):
            if campaign_id == 5:
                # Simulate RPC failure for campaign 5
                return None  # Current behavior returns None on failure
            return {"id": campaign_id, "campaign": {"gauge": "0x123"}, "periods": []}

        with patch.object(
            service, "_fetch_single_campaign", side_effect=mock_fetch_single
        ):
            result = await service._fetch_campaigns_by_ids(
                web3_service=MagicMock(),
                bytecode_data={},
                platform_address="0x123",
                campaign_ids=[1, 2, 3, 4, 5, 6, 7],
            )

            # Current behavior: [c for c in results if c is not None]
            # Campaign 5 failure is silently swallowed

            # The method currently returns a raw list
            if isinstance(result, list):
                # Check that we lost campaign 5 silently
                returned_ids = {c["id"] for c in result}
                if 5 not in returned_ids and len(result) == 6:
                    # This confirms the bug - campaign 5 was silently dropped
                    pytest.fail(
                        "Campaign 5 was silently dropped. "
                        "_fetch_campaigns_by_ids should return Result type "
                        "with partial_success indicating which campaigns failed."
                    )

            # Expected new behavior
            if isinstance(result, Result):
                if hasattr(result, "failed_items"):
                    failed_campaign_ids = [
                        item.get("campaign_id") for item in result.failed_items
                    ]
                    assert 5 in failed_campaign_ids, (
                        "Failed campaign ID should be tracked."
                    )

    @pytest.mark.asyncio
    async def test_multiple_campaign_fetch_failures_all_tracked(self):
        """All campaign fetch failures should be tracked, not just the first."""
        from votemarket_toolkit.campaigns.service import CampaignService

        service = CampaignService()

        failed_ids = {3, 5, 7}

        async def mock_fetch_single(
            web3_service, bytecode_data, platform_address, campaign_id, **kwargs
        ):
            if campaign_id in failed_ids:
                return None  # Simulate failure
            return {"id": campaign_id, "campaign": {"gauge": "0x123"}, "periods": []}

        with patch.object(
            service, "_fetch_single_campaign", side_effect=mock_fetch_single
        ):
            result = await service._fetch_campaigns_by_ids(
                web3_service=MagicMock(),
                bytecode_data={},
                platform_address="0x123",
                campaign_ids=list(range(10)),
            )

            # Current: None values filtered, no tracking
            if isinstance(result, list):
                returned_ids = {c["id"] for c in result}
                missing_ids = set(range(10)) - returned_ids

                if missing_ids == failed_ids:
                    pytest.fail(
                        f"Campaigns {failed_ids} were silently dropped. "
                        f"Method should return Result with tracked failures."
                    )

            # Expected: All failures tracked in Result
            if isinstance(result, Result) and hasattr(result, "failed_items"):
                tracked_failed_ids = {
                    item.get("campaign_id") for item in result.failed_items
                }
                assert tracked_failed_ids == failed_ids, (
                    f"All failed IDs should be tracked. "
                    f"Expected {failed_ids}, got {tracked_failed_ids}"
                )


class TestCampaignServiceResultType:
    """
    Test that CampaignService methods return proper Result types.

    Current behavior:
    - Some methods return raw data types
    - Error information is lost

    Expected behavior:
    - All public methods return Result[T]
    - Errors are always captured
    """

    @pytest.mark.asyncio
    async def test_get_campaigns_returns_result_with_errors(self):
        """get_campaigns should include errors in Result even on partial success."""
        from votemarket_toolkit.campaigns.service import CampaignService

        service = CampaignService()

        # Mock the internal method to return partial data with errors
        campaigns_data = [{"id": 1}, {"id": 2}]

        with patch.object(
            service, "_fetch_campaigns_by_ids"
        ) as mock_fetch, patch(
            "votemarket_toolkit.shared.services.web3_service.Web3Service.get_instance"
        ) as mock_ws:
            mock_ws.return_value = MagicMock()

            # Simulate some campaigns fetched but with error during fetch
            mock_fetch.return_value = campaigns_data

            # Trigger an error in proof population
            with patch.object(
                service, "_populate_proof_status_flags"
            ) as mock_populate:
                mock_populate.side_effect = Exception("Oracle error")

                result = await service.get_campaigns(
                    chain_id=1,
                    platform_address="0x123",
                    check_proofs=True,
                )

                # The outer result should indicate errors occurred
                # Currently the bare except swallows this
                assert result.has_errors() or result.has_warnings(), (
                    "Errors from inner operations should propagate to outer Result"
                )

    @pytest.mark.asyncio
    async def test_get_campaigns_error_context_includes_platform(self):
        """Errors should include platform address for debugging."""
        from votemarket_toolkit.campaigns.service import CampaignService

        service = CampaignService()

        platform = "0x000000073D065Fc33a3050C2d4a8e82EE5C5C25a"

        with patch.object(
            service, "_fetch_campaigns_by_ids"
        ) as mock_fetch, patch(
            "votemarket_toolkit.shared.services.web3_service.Web3Service.get_instance"
        ) as mock_ws:
            mock_ws.return_value = MagicMock()
            mock_fetch.side_effect = Exception("Total failure")

            result = await service.get_campaigns(
                chain_id=1,
                platform_address=platform,
            )

            # Error context should include platform
            if result.errors:
                error_str = str(result.errors)
                platform_in_error = platform in error_str or platform.lower() in error_str
                assert platform_in_error, (
                    "Error context should include platform address for debugging"
                )


class TestErrorLoggingLevels:
    """
    Test that errors are logged at appropriate levels.

    Current behavior (BUG):
    - Many errors logged at DEBUG level
    - Production logs miss important failures

    Expected behavior:
    - RPC failures: WARNING minimum
    - Data corruption: ERROR
    - System failures: CRITICAL
    """

    @pytest.mark.asyncio
    async def test_rpc_failures_logged_as_warning(self):
        """RPC failures should be logged at WARNING level minimum."""
        from votemarket_toolkit.campaigns.service import CampaignService

        with patch("votemarket_toolkit.campaigns.service._logger") as mock_logger:
            service = CampaignService()

            # Trigger an RPC failure via _get_active_campaign_ids
            mock_web3_service = MagicMock()
            mock_web3_service.w3.eth.call.side_effect = Exception("RPC down")

            await service._get_active_campaign_ids(
                web3_service=mock_web3_service,
                bytecode_data={"active_ids": "0x" + "00" * 100},
                platform_address="0x123",
                total_campaigns=10,
            )

            # Check that warning or error was called, not just debug
            warning_or_error_called = (
                mock_logger.warning.called or mock_logger.error.called
            )
            assert warning_or_error_called, (
                "RPC failures should be logged at WARNING or ERROR level. "
                "Currently uses _logger.debug() which is too quiet for production."
            )
