"""
Unit tests for Result type enhancements.

These tests verify the Result type supports:
1. partial_success mode - when some items succeed and some fail
2. degraded mode - when fallback data is used
3. Proper error aggregation and reporting

These tests should FAIL against the current implementation.
The tests define the DESIRED behavior after the refactor.
"""

import pytest
from dataclasses import dataclass
from typing import List, Optional

from votemarket_toolkit.shared.results import (
    ErrorSeverity,
    ProcessingError,
    Result,
)


class TestResultBasicBehavior:
    """Test basic Result type behavior."""

    def test_ok_result_is_successful(self):
        """Result.ok() should create a successful result."""
        result = Result.ok("test data")

        assert result.success is True
        assert result.data == "test data"
        assert len(result.errors) == 0

    def test_fail_result_is_not_successful(self):
        """Result.fail() should create a failed result."""
        error = ProcessingError(
            source="test",
            message="Test error",
            severity=ErrorSeverity.ERROR,
        )
        result = Result.fail(error)

        assert result.success is False
        assert result.data is None
        assert len(result.errors) == 1
        assert result.errors[0].message == "Test error"

    def test_unwrap_returns_data_on_success(self):
        """unwrap() should return data for successful results."""
        result = Result.ok({"key": "value"})

        data = result.unwrap()

        assert data == {"key": "value"}

    def test_unwrap_raises_on_failure(self):
        """unwrap() should raise for failed results."""
        error = ProcessingError(
            source="test",
            message="Expected error",
            severity=ErrorSeverity.ERROR,
        )
        result = Result.fail(error)

        with pytest.raises(RuntimeError, match="Expected error"):
            result.unwrap()

    def test_add_warning_preserves_success(self):
        """Adding a warning should not change success status."""
        result = Result.ok("data")
        result.add_warning(
            source="test",
            message="This is a warning",
            context={"key": "value"},
        )

        assert result.success is True
        assert result.data == "data"
        assert result.has_warnings() is True
        assert result.has_errors() is False


class TestResultPartialSuccess:
    """
    Test Result.partial_success mode.

    Partial success is when an operation completes but with some failures.
    For example: fetching 100 campaigns but 5 RPC calls failed.

    EXPECTED BEHAVIOR (tests should FAIL until implemented):
    - partial_success flag distinguishes from full success
    - Callers can detect partial success vs full success
    - Error details are preserved for failed items
    """

    def test_partial_success_creates_result_with_partial_flag(self):
        """Result.partial_success() should create a result with partial flag."""
        campaigns = [{"id": 1}, {"id": 2}, {"id": 3}]
        errors = [
            ProcessingError(
                source="campaign_fetch",
                message="Failed to fetch campaign 4",
                severity=ErrorSeverity.ERROR,
                context={"campaign_id": 4},
            )
        ]

        # This method should exist after the refactor
        result = Result.partial_success(data=campaigns, errors=errors)

        assert result.success is True  # Operation completed
        assert result.is_partial is True  # But with partial data
        assert result.data == campaigns
        assert len(result.errors) == 1

    def test_partial_success_distinguishable_from_full_success(self):
        """Partial success should be distinguishable from full success."""
        full_result = Result.ok([{"id": 1}, {"id": 2}])
        partial_result = Result.partial_success(
            data=[{"id": 1}],
            errors=[
                ProcessingError(
                    source="test",
                    message="Item 2 failed",
                    severity=ErrorSeverity.ERROR,
                )
            ],
        )

        assert full_result.is_partial is False
        assert partial_result.is_partial is True

    def test_partial_success_preserves_failed_item_context(self):
        """Partial success should preserve context about failed items."""
        errors = [
            ProcessingError(
                source="campaign_fetch",
                message="RPC timeout",
                severity=ErrorSeverity.ERROR,
                context={
                    "campaign_id": 42,
                    "platform": "0x1234",
                    "retry_count": 3,
                },
            )
        ]
        result = Result.partial_success(data=[], errors=errors)

        assert result.errors[0].context["campaign_id"] == 42
        assert result.errors[0].context["retry_count"] == 3

    def test_partial_success_success_rate(self):
        """Partial success should report success rate."""
        result = Result.partial_success(
            data=[{"id": 1}, {"id": 2}, {"id": 3}],
            errors=[
                ProcessingError(
                    source="test",
                    message="Failed 1",
                    severity=ErrorSeverity.ERROR,
                ),
                ProcessingError(
                    source="test",
                    message="Failed 2",
                    severity=ErrorSeverity.ERROR,
                ),
            ],
            total_attempted=5,
        )

        assert result.success_count == 3
        assert result.failure_count == 2
        assert result.total_attempted == 5
        assert result.success_rate == 0.6  # 3/5


class TestResultDegradedMode:
    """
    Test Result.degraded mode.

    Degraded mode is when a fallback strategy was used due to primary failure.
    For example: vector search failed, fell back to substring search.

    EXPECTED BEHAVIOR (tests should FAIL until implemented):
    - degraded flag indicates fallback was used
    - Original error is preserved
    - Fallback strategy is documented
    """

    def test_degraded_creates_result_with_degraded_flag(self):
        """Result.degraded() should create a result with degraded flag."""
        fallback_data = [{"id": 1, "name": "Fallback result"}]
        original_error = ProcessingError(
            source="vector_search",
            message="Redis connection failed",
            severity=ErrorSeverity.ERROR,
        )

        result = Result.degraded(
            data=fallback_data,
            original_error=original_error,
            fallback_strategy="substring_search",
        )

        assert result.success is True
        assert result.is_degraded is True
        assert result.data == fallback_data
        assert result.fallback_strategy == "substring_search"
        assert len(result.errors) == 1  # Original error preserved

    def test_degraded_distinguishable_from_normal_success(self):
        """Degraded result should be distinguishable from normal success."""
        normal_result = Result.ok(["data"])
        degraded_result = Result.degraded(
            data=["fallback"],
            original_error=ProcessingError(
                source="test",
                message="Primary failed",
                severity=ErrorSeverity.ERROR,
            ),
            fallback_strategy="fallback_method",
        )

        assert normal_result.is_degraded is False
        assert degraded_result.is_degraded is True

    def test_degraded_preserves_original_error_chain(self):
        """Degraded result should preserve the original error."""
        original_exception = ConnectionError("Redis down")
        original_error = ProcessingError(
            source="redis",
            message="Connection failed",
            severity=ErrorSeverity.ERROR,
            exception=original_exception,
        )

        result = Result.degraded(
            data=["fallback"],
            original_error=original_error,
            fallback_strategy="db_query",
        )

        assert result.errors[0].exception is original_exception
        assert result.errors[0].source == "redis"


class TestResultErrorAggregation:
    """
    Test error aggregation in Result.

    Results should support collecting multiple errors from batch operations.

    EXPECTED BEHAVIOR (tests should FAIL until implemented):
    - Multiple errors can be aggregated
    - Errors can be filtered by severity
    - Errors can be grouped by source
    """

    def test_aggregate_errors_from_multiple_results(self):
        """Should aggregate errors from multiple Result objects."""
        result1 = Result.fail(
            ProcessingError(
                source="gauge_1",
                message="RPC error",
                severity=ErrorSeverity.ERROR,
            )
        )
        result2 = Result.fail(
            ProcessingError(
                source="gauge_2",
                message="Timeout",
                severity=ErrorSeverity.ERROR,
            )
        )
        result3 = Result.ok("success")

        # Aggregate errors from multiple results
        aggregated = Result.aggregate([result1, result2, result3])

        assert len(aggregated.errors) == 2
        sources = {e.source for e in aggregated.errors}
        assert sources == {"gauge_1", "gauge_2"}

    def test_filter_errors_by_severity(self):
        """Should be able to filter errors by severity."""
        result = Result.ok("data")
        result.add_warning(source="test", message="Warning 1")
        result.add_error(
            ProcessingError(
                source="test",
                message="Error 1",
                severity=ErrorSeverity.ERROR,
            )
        )
        result.add_error(
            ProcessingError(
                source="test",
                message="Critical 1",
                severity=ErrorSeverity.CRITICAL,
            )
        )

        warnings = result.get_errors_by_severity(ErrorSeverity.WARNING)
        errors = result.get_errors_by_severity(ErrorSeverity.ERROR)
        criticals = result.get_errors_by_severity(ErrorSeverity.CRITICAL)

        assert len(warnings) == 1
        assert len(errors) == 1
        assert len(criticals) == 1

    def test_group_errors_by_source(self):
        """Should be able to group errors by source."""
        result = Result.ok("data")
        result.add_error(
            ProcessingError(
                source="rpc",
                message="RPC error 1",
                severity=ErrorSeverity.ERROR,
            )
        )
        result.add_error(
            ProcessingError(
                source="rpc",
                message="RPC error 2",
                severity=ErrorSeverity.ERROR,
            )
        )
        result.add_error(
            ProcessingError(
                source="validation",
                message="Validation error",
                severity=ErrorSeverity.ERROR,
            )
        )

        grouped = result.group_errors_by_source()

        assert len(grouped["rpc"]) == 2
        assert len(grouped["validation"]) == 1


class TestProcessingReport:
    """
    Test ProcessingReport for central error tracking.

    ProcessingReport is a new type that aggregates results from
    complex multi-step operations.

    EXPECTED BEHAVIOR (tests should FAIL until implemented):
    - Tracks results from multiple processing steps
    - Provides summary statistics
    - Supports serialization for logging/reporting
    """

    def test_processing_report_tracks_multiple_phases(self):
        """ProcessingReport should track results from multiple phases."""
        from votemarket_toolkit.shared.results import ProcessingReport

        report = ProcessingReport(operation="proof_generation")

        report.add_phase_result(
            phase="gauge_validation",
            result=Result.ok({"validated": 10}),
        )
        report.add_phase_result(
            phase="proof_generation",
            result=Result.partial_success(
                data={"generated": 8},
                errors=[
                    ProcessingError(
                        source="proof",
                        message="Failed 2",
                        severity=ErrorSeverity.ERROR,
                    )
                ],
            ),
        )

        assert report.has_phase("gauge_validation")
        assert report.has_phase("proof_generation")
        assert report.get_phase_result("gauge_validation").success is True

    def test_processing_report_summary_statistics(self):
        """ProcessingReport should provide summary statistics."""
        from votemarket_toolkit.shared.results import ProcessingReport

        report = ProcessingReport(operation="batch_fetch")

        # Add various results
        for i in range(5):
            if i < 3:
                report.add_phase_result(
                    phase=f"batch_{i}",
                    result=Result.ok({"count": 10}),
                )
            else:
                report.add_phase_result(
                    phase=f"batch_{i}",
                    result=Result.fail(
                        ProcessingError(
                            source="rpc",
                            message=f"Batch {i} failed",
                            severity=ErrorSeverity.ERROR,
                        )
                    ),
                )

        summary = report.get_summary()

        assert summary["total_phases"] == 5
        assert summary["successful_phases"] == 3
        assert summary["failed_phases"] == 2
        assert summary["success_rate"] == 0.6

    def test_processing_report_serialization(self):
        """ProcessingReport should serialize to dict for logging."""
        from votemarket_toolkit.shared.results import ProcessingReport

        report = ProcessingReport(operation="test_op")
        report.add_phase_result(
            phase="step1",
            result=Result.ok("data"),
        )

        serialized = report.to_dict()

        assert serialized["operation"] == "test_op"
        assert "phases" in serialized
        assert "step1" in serialized["phases"]


class TestValidationGate:
    """
    Test ValidationGate for input/output validation.

    ValidationGate validates data at boundaries to ensure
    fail-closed behavior.

    EXPECTED BEHAVIOR (tests should FAIL until implemented):
    - Validates inputs before processing
    - Validates outputs before returning
    - Fails fast with clear error messages
    """

    def test_validation_gate_validates_input(self):
        """ValidationGate should validate inputs."""
        from votemarket_toolkit.shared.results import ValidationGate

        @dataclass
        class CampaignInput:
            campaign_id: int
            platform_address: str

        gate = ValidationGate()

        # Valid input
        valid_result = gate.validate_input(
            CampaignInput(campaign_id=1, platform_address="0x1234")
        )
        assert valid_result.success is True

        # Invalid input (negative campaign_id)
        invalid_result = gate.validate_input(
            CampaignInput(campaign_id=-1, platform_address="0x1234")
        )
        assert invalid_result.success is False
        assert "campaign_id" in invalid_result.errors[0].message.lower()

    def test_validation_gate_validates_output(self):
        """ValidationGate should validate outputs."""
        from votemarket_toolkit.shared.results import ValidationGate

        gate = ValidationGate()

        # Valid output
        valid_campaigns = [{"id": 1, "gauge": "0x123"}]
        valid_result = gate.validate_output(valid_campaigns, schema="campaign_list")
        assert valid_result.success is True

        # Invalid output (missing required field)
        invalid_campaigns = [{"id": 1}]  # Missing gauge
        invalid_result = gate.validate_output(
            invalid_campaigns, schema="campaign_list"
        )
        assert invalid_result.success is False

    def test_validation_gate_fail_closed_on_validation_error(self):
        """ValidationGate should fail-closed on validation errors."""
        from votemarket_toolkit.shared.results import ValidationGate

        gate = ValidationGate()

        # Simulate validation function that raises
        def bad_validator(data):
            raise ValueError("Validation crashed")

        result = gate.validate_with_custom(
            data={"test": "data"},
            validator=bad_validator,
        )

        # Should fail, not succeed by default
        assert result.success is False
        assert "validation" in result.errors[0].source.lower()
