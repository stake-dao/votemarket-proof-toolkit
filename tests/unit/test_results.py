"""
Unit tests for the Result types module.
"""

import pytest

from votemarket_toolkit.shared.results import (
    ErrorSeverity,
    ProcessingError,
    ProofGenerationSummary,
    Result,
)


class TestProcessingError:
    """Tests for ProcessingError dataclass."""

    def test_create_error(self):
        """Test creating a processing error."""
        error = ProcessingError(
            source="test",
            message="Test error message",
            severity=ErrorSeverity.ERROR,
        )
        assert error.source == "test"
        assert error.message == "Test error message"
        assert error.severity == ErrorSeverity.ERROR
        assert error.context == {}
        assert error.exception is None

    def test_create_error_with_context(self):
        """Test creating an error with context."""
        error = ProcessingError(
            source="gauge_proof",
            message="RPC failed",
            severity=ErrorSeverity.ERROR,
            context={"gauge": "0x123", "epoch": 1764806400},
        )
        assert error.context["gauge"] == "0x123"
        assert error.context["epoch"] == 1764806400

    def test_create_error_with_exception(self):
        """Test creating an error with exception."""
        original_exception = ValueError("original error")
        error = ProcessingError(
            source="test",
            message="Wrapped error",
            severity=ErrorSeverity.CRITICAL,
            exception=original_exception,
        )
        assert error.exception is original_exception

    def test_to_dict(self):
        """Test converting error to dictionary."""
        error = ProcessingError(
            source="test",
            message="Test error",
            severity=ErrorSeverity.WARNING,
            context={"key": "value"},
        )
        d = error.to_dict()
        assert d["source"] == "test"
        assert d["message"] == "Test error"
        assert d["severity"] == "warning"
        assert d["context"] == {"key": "value"}


class TestResult:
    """Tests for Result[T] generic class."""

    def test_ok_result(self):
        """Test creating a successful result."""
        result = Result.ok({"data": "test"})
        assert result.success is True
        assert result.data == {"data": "test"}
        assert result.errors == []

    def test_ok_result_with_none(self):
        """Test creating a successful result with None data."""
        result = Result.ok(None)
        assert result.success is True
        assert result.data is None

    def test_fail_result(self):
        """Test creating a failed result."""
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

    def test_fail_with_message(self):
        """Test convenience method for creating failed result."""
        result = Result.fail_with_message(
            source="test",
            message="Quick error",
            severity=ErrorSeverity.ERROR,
            context={"key": "value"},
        )
        assert result.success is False
        assert result.errors[0].source == "test"
        assert result.errors[0].message == "Quick error"
        assert result.errors[0].context["key"] == "value"

    def test_add_error(self):
        """Test adding an error to a result."""
        result = Result.ok("data")
        error = ProcessingError(
            source="test",
            message="warning",
            severity=ErrorSeverity.WARNING,
        )
        result.add_error(error)
        assert result.success is True  # Still success, just has warnings
        assert len(result.errors) == 1

    def test_add_warning(self):
        """Test convenience method for adding warning."""
        result = Result.ok("data")
        result.add_warning(
            source="test",
            message="This is a warning",
            context={"key": "value"},
        )
        assert result.success is True
        assert len(result.errors) == 1
        assert result.errors[0].severity == ErrorSeverity.WARNING

    def test_has_errors_with_errors(self):
        """Test has_errors when errors exist."""
        result = Result.fail_with_message(
            source="test", message="error", severity=ErrorSeverity.ERROR
        )
        assert result.has_errors() is True

    def test_has_errors_with_only_warnings(self):
        """Test has_errors when only warnings exist."""
        result = Result.ok("data")
        result.add_warning(source="test", message="warning")
        assert result.has_errors() is False

    def test_has_errors_with_critical(self):
        """Test has_errors with critical severity."""
        result = Result.fail_with_message(
            source="test", message="critical", severity=ErrorSeverity.CRITICAL
        )
        assert result.has_errors() is True

    def test_has_warnings(self):
        """Test has_warnings method."""
        result = Result.ok("data")
        assert result.has_warnings() is False
        result.add_warning(source="test", message="warning")
        assert result.has_warnings() is True

    def test_get_error_messages(self):
        """Test getting all error messages."""
        result = Result.ok("data")
        result.add_warning(source="test1", message="warning 1")
        result.add_error(
            ProcessingError(
                source="test2", message="error 2", severity=ErrorSeverity.ERROR
            )
        )
        messages = result.get_error_messages()
        assert len(messages) == 2
        assert "warning 1" in messages
        assert "error 2" in messages


class TestProofGenerationSummary:
    """Tests for ProofGenerationSummary dataclass."""

    def test_create_summary(self):
        """Test creating a proof generation summary."""
        summary = ProofGenerationSummary(protocol="curve", epoch=1764806400)
        assert summary.protocol == "curve"
        assert summary.epoch == 1764806400
        assert summary.platforms_processed == 0
        assert summary.gauges_failed == 0
        assert summary.errors == []

    def test_add_error(self):
        """Test adding an error to summary."""
        summary = ProofGenerationSummary(protocol="test", epoch=123)
        error = ProcessingError(
            source="test", message="error", severity=ErrorSeverity.ERROR
        )
        summary.add_error(error)
        assert len(summary.errors) == 1

    def test_add_error_from_result(self):
        """Test adding errors from a Result."""
        summary = ProofGenerationSummary(protocol="test", epoch=123)
        result = Result.ok("data")
        result.add_warning(source="test1", message="warning")
        result.add_error(
            ProcessingError(
                source="test2", message="error", severity=ErrorSeverity.ERROR
            )
        )
        summary.add_error_from_result(result)
        assert len(summary.errors) == 2

    def test_has_critical_errors_false(self):
        """Test has_critical_errors when no critical errors."""
        summary = ProofGenerationSummary(protocol="test", epoch=123)
        assert summary.has_critical_errors() is False

        summary.add_error(
            ProcessingError(
                source="test", message="error", severity=ErrorSeverity.ERROR
            )
        )
        assert summary.has_critical_errors() is False

    def test_has_critical_errors_true(self):
        """Test has_critical_errors when critical error exists."""
        summary = ProofGenerationSummary(protocol="test", epoch=123)
        summary.add_error(
            ProcessingError(
                source="test",
                message="critical",
                severity=ErrorSeverity.CRITICAL,
            )
        )
        assert summary.has_critical_errors() is True

    def test_has_errors(self):
        """Test has_errors method."""
        summary = ProofGenerationSummary(protocol="test", epoch=123)
        assert summary.has_errors() is False

        summary.add_error(
            ProcessingError(
                source="test", message="error", severity=ErrorSeverity.ERROR
            )
        )
        assert summary.has_errors() is True

    def test_error_count(self):
        """Test error_count method."""
        summary = ProofGenerationSummary(protocol="test", epoch=123)
        summary.add_error(
            ProcessingError(
                source="test1", message="error", severity=ErrorSeverity.ERROR
            )
        )
        summary.add_error(
            ProcessingError(
                source="test2",
                message="warning",
                severity=ErrorSeverity.WARNING,
            )
        )
        summary.add_error(
            ProcessingError(
                source="test3",
                message="critical",
                severity=ErrorSeverity.CRITICAL,
            )
        )
        # Only ERROR and CRITICAL count
        assert summary.error_count() == 2

    def test_warning_count(self):
        """Test warning_count method."""
        summary = ProofGenerationSummary(protocol="test", epoch=123)
        summary.add_error(
            ProcessingError(
                source="test1",
                message="warning1",
                severity=ErrorSeverity.WARNING,
            )
        )
        summary.add_error(
            ProcessingError(
                source="test2",
                message="warning2",
                severity=ErrorSeverity.WARNING,
            )
        )
        summary.add_error(
            ProcessingError(
                source="test3", message="error", severity=ErrorSeverity.ERROR
            )
        )
        assert summary.warning_count() == 2

    def test_to_dict(self):
        """Test converting summary to dictionary."""
        summary = ProofGenerationSummary(
            protocol="curve",
            epoch=1764806400,
            platforms_processed=5,
            platforms_skipped=1,
            gauges_processed=10,
            gauges_failed=2,
        )
        d = summary.to_dict()
        assert d["protocol"] == "curve"
        assert d["epoch"] == 1764806400
        assert d["success_rate"]["platforms"] == "5/6"
        assert d["success_rate"]["gauges"] == "10/12"
        assert d["counts"]["platforms_processed"] == 5

    def test_to_dict_with_no_totals(self):
        """Test to_dict when totals are zero."""
        summary = ProofGenerationSummary(protocol="test", epoch=123)
        d = summary.to_dict()
        assert d["success_rate"]["platforms"] == "N/A"
        assert d["success_rate"]["gauges"] == "N/A"

    def test_merge(self):
        """Test merging two summaries."""
        summary1 = ProofGenerationSummary(
            protocol="curve",
            epoch=1764806400,
            platforms_processed=3,
            gauges_processed=10,
            users_processed=100,
        )
        summary2 = ProofGenerationSummary(
            protocol="curve",
            epoch=1764806400,
            platforms_processed=2,
            gauges_processed=5,
            users_processed=50,
            gauges_failed=1,
        )
        summary2.add_error(
            ProcessingError(
                source="test", message="error", severity=ErrorSeverity.ERROR
            )
        )

        summary1.merge(summary2)

        assert summary1.platforms_processed == 5
        assert summary1.gauges_processed == 15
        assert summary1.users_processed == 150
        assert summary1.gauges_failed == 1
        assert len(summary1.errors) == 1
