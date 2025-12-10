"""
Result types for explicit success/failure tracking in proof generation.

This module provides structured result types that carry success/failure
information, enabling zero silent failures during proof generation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")


class ErrorSeverity(Enum):
    """Severity levels for processing errors."""

    WARNING = "warning"  # Continue processing, log issue
    ERROR = "error"  # Skip this item, continue others
    CRITICAL = "critical"  # Stop processing entirely


@dataclass
class ProcessingError:
    """
    Represents a single processing error with context.

    Attributes:
        source: Component that generated the error (e.g., "gauge_proof", "user_proof")
        message: Human-readable error description
        severity: How severe the error is (affects control flow)
        context: Additional context like gauge_address, user, epoch
        exception: Original exception if available
    """

    source: str
    message: str
    severity: ErrorSeverity
    context: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[Exception] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source": self.source,
            "message": self.message,
            "severity": self.severity.value,
            "context": self.context,
        }


@dataclass
class Result(Generic[T]):
    """
    Result type that carries success/failure information.

    This is a simple Result/Either monad pattern that makes error handling
    explicit and prevents silent failures.

    Attributes:
        success: Whether the operation succeeded
        data: The result data if successful
        errors: List of errors encountered (can have errors even on success for warnings)
    """

    success: bool
    data: Optional[T] = None
    errors: List[ProcessingError] = field(default_factory=list)

    @classmethod
    def ok(cls, data: T) -> "Result[T]":
        """Create a successful result with data."""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: ProcessingError) -> "Result[T]":
        """Create a failed result with an error."""
        return cls(success=False, errors=[error])

    @classmethod
    def fail_with_message(
        cls,
        source: str,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ) -> "Result[T]":
        """Create a failed result with a message (convenience method)."""
        error = ProcessingError(
            source=source,
            message=message,
            severity=severity,
            context=context or {},
            exception=exception,
        )
        return cls(success=False, errors=[error])

    def add_error(self, error: ProcessingError) -> "Result[T]":
        """Add an error to the result (for warnings on success)."""
        self.errors.append(error)
        return self

    def add_warning(
        self,
        source: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> "Result[T]":
        """Add a warning to the result (convenience method)."""
        self.errors.append(
            ProcessingError(
                source=source,
                message=message,
                severity=ErrorSeverity.WARNING,
                context=context or {},
            )
        )
        return self

    def has_errors(self) -> bool:
        """Check if result has any ERROR or CRITICAL level errors."""
        return any(
            e.severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL)
            for e in self.errors
        )

    def has_warnings(self) -> bool:
        """Check if result has any WARNING level errors."""
        return any(e.severity == ErrorSeverity.WARNING for e in self.errors)

    def get_error_messages(self) -> List[str]:
        """Get all error messages as strings."""
        return [e.message for e in self.errors]


@dataclass
class ProofGenerationSummary:
    """
    Summary of a proof generation run.

    This provides a complete picture of what happened during proof generation,
    including success/failure counts and detailed error information.
    """

    protocol: str
    epoch: int

    # Counts
    platforms_processed: int = 0
    platforms_skipped: int = 0
    campaigns_processed: int = 0
    campaigns_skipped: int = 0
    gauges_processed: int = 0
    gauges_failed: int = 0
    users_processed: int = 0
    users_failed: int = 0
    listed_users_processed: int = 0
    listed_users_failed: int = 0

    # Details
    errors: List[ProcessingError] = field(default_factory=list)
    skipped_platforms: List[Dict[str, Any]] = field(default_factory=list)
    skipped_campaigns: List[Dict[str, Any]] = field(default_factory=list)
    failed_gauges: List[Dict[str, Any]] = field(default_factory=list)
    failed_users: List[Dict[str, Any]] = field(default_factory=list)

    def add_error(self, error: ProcessingError) -> None:
        """Add an error to the summary."""
        self.errors.append(error)

    def add_error_from_result(self, result: Result) -> None:
        """Add all errors from a Result to the summary."""
        self.errors.extend(result.errors)

    def has_critical_errors(self) -> bool:
        """Check if any critical errors occurred."""
        return any(e.severity == ErrorSeverity.CRITICAL for e in self.errors)

    def has_errors(self) -> bool:
        """Check if any errors (not just warnings) occurred."""
        return any(
            e.severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL)
            for e in self.errors
        )

    def error_count(self) -> int:
        """Count total errors (excluding warnings)."""
        return sum(
            1
            for e in self.errors
            if e.severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL)
        )

    def warning_count(self) -> int:
        """Count total warnings."""
        return sum(
            1 for e in self.errors if e.severity == ErrorSeverity.WARNING
        )

    def _calculate_rate(self, success: int, failed: int) -> str:
        """Calculate success rate as string."""
        total = success + failed
        if total == 0:
            return "N/A"
        return f"{success}/{total}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary for JSON serialization."""
        return {
            "protocol": self.protocol,
            "epoch": self.epoch,
            "success_rate": {
                "platforms": self._calculate_rate(
                    self.platforms_processed, self.platforms_skipped
                ),
                "campaigns": self._calculate_rate(
                    self.campaigns_processed, self.campaigns_skipped
                ),
                "gauges": self._calculate_rate(
                    self.gauges_processed, self.gauges_failed
                ),
                "users": self._calculate_rate(
                    self.users_processed, self.users_failed
                ),
                "listed_users": self._calculate_rate(
                    self.listed_users_processed, self.listed_users_failed
                ),
            },
            "counts": {
                "platforms_processed": self.platforms_processed,
                "platforms_skipped": self.platforms_skipped,
                "campaigns_processed": self.campaigns_processed,
                "campaigns_skipped": self.campaigns_skipped,
                "gauges_processed": self.gauges_processed,
                "gauges_failed": self.gauges_failed,
                "users_processed": self.users_processed,
                "users_failed": self.users_failed,
                "listed_users_processed": self.listed_users_processed,
                "listed_users_failed": self.listed_users_failed,
            },
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "errors": [e.to_dict() for e in self.errors],
            "failed_gauges": self.failed_gauges,
            "failed_users": self.failed_users[:100],  # Limit for large runs
        }

    def merge(self, other: "ProofGenerationSummary") -> None:
        """Merge another summary into this one."""
        self.platforms_processed += other.platforms_processed
        self.platforms_skipped += other.platforms_skipped
        self.campaigns_processed += other.campaigns_processed
        self.campaigns_skipped += other.campaigns_skipped
        self.gauges_processed += other.gauges_processed
        self.gauges_failed += other.gauges_failed
        self.users_processed += other.users_processed
        self.users_failed += other.users_failed
        self.listed_users_processed += other.listed_users_processed
        self.listed_users_failed += other.listed_users_failed
        self.errors.extend(other.errors)
        self.skipped_platforms.extend(other.skipped_platforms)
        self.skipped_campaigns.extend(other.skipped_campaigns)
        self.failed_gauges.extend(other.failed_gauges)
        self.failed_users.extend(other.failed_users)
