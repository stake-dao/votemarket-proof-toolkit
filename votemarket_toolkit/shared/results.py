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
        partial: Whether this is a partial success (some items failed)
        degraded: Whether data may be incomplete (fallback was used)
    """

    success: bool
    data: Optional[T] = None
    errors: List[ProcessingError] = field(default_factory=list)
    _partial: bool = False
    _degraded: bool = False
    _total_attempted: int = 0
    _succeeded_count: int = 0
    _fallback_strategy: Optional[str] = None

    @property
    def is_partial(self) -> bool:
        """Check if this is a partial success result."""
        return self._partial

    @property
    def partial(self) -> bool:
        """Check if this is a partial success result (alias)."""
        return self._partial

    @property
    def is_degraded(self) -> bool:
        """Check if this result is in degraded mode."""
        return self._degraded

    @property
    def degraded(self) -> bool:
        """Check if this result is in degraded mode (alias)."""
        return self._degraded

    @property
    def fallback_strategy(self) -> Optional[str]:
        """Get the fallback strategy used for degraded result."""
        return self._fallback_strategy

    @property
    def success_rate(self) -> float:
        """Calculate success rate for partial results."""
        if self._total_attempted == 0:
            return 1.0 if self.success else 0.0
        return self._succeeded_count / self._total_attempted

    @property
    def success_count(self) -> int:
        """Get count of successful items."""
        return self._succeeded_count

    @property
    def failure_count(self) -> int:
        """Get count of failed items."""
        return self._total_attempted - self._succeeded_count

    @property
    def total_attempted(self) -> int:
        """Get total items attempted."""
        return self._total_attempted

    @classmethod
    def ok(cls, data: T) -> "Result[T]":
        """Create a successful result with data."""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: ProcessingError) -> "Result[T]":
        """Create a failed result with an error."""
        return cls(success=False, errors=[error])

    @classmethod
    def partial_success(
        cls,
        data: T,
        errors: List[ProcessingError],
        total_attempted: int = 0,
        succeeded_count: int = 0,
    ) -> "Result[T]":
        """
        Create a result with data but also errors (partial success).

        Use this when a batch operation partially succeeded - some items
        processed successfully but others failed.
        """
        result = cls(success=True, data=data, errors=errors, _partial=True)
        result._total_attempted = total_attempted
        # Auto-calculate succeeded_count if not provided
        if succeeded_count == 0 and isinstance(data, list):
            result._succeeded_count = len(data)
        else:
            result._succeeded_count = succeeded_count
        return result

    @classmethod
    def degraded(
        cls,
        data: T,
        reason: str = "",
        fallback_used: Optional[str] = None,
        original_error: Optional[ProcessingError] = None,
        fallback_strategy: Optional[str] = None,
    ) -> "Result[T]":
        """
        Create a result with potentially incomplete data.

        Use this when a fallback was used or data may be missing.
        The operation "succeeded" but callers should know the data
        quality may be reduced.
        """
        result = cls(success=True, data=data, _degraded=True)
        result._fallback_strategy = fallback_strategy or fallback_used
        if original_error:
            result.errors.append(original_error)
        if reason:
            result.add_warning(
                source="degraded_mode",
                message=reason,
                context={"fallback_strategy": result._fallback_strategy}
                if result._fallback_strategy
                else None,
            )
        return result

    @classmethod
    def degraded_result(cls, data: T, reason: str) -> "Result[T]":
        """Alias for degraded() for backwards compatibility."""
        return cls.degraded(data, reason=reason)

    @classmethod
    def aggregate(cls, results: List["Result"]) -> "Result[List[Any]]":
        """
        Aggregate multiple results into a single result.

        Collects all successful data and all errors from the input results.
        """
        all_data = []
        all_errors = []
        has_failures = False

        for result in results:
            if result.success and result.data is not None:
                all_data.append(result.data)
            if not result.success:
                has_failures = True
            all_errors.extend(result.errors)

        if has_failures:
            return cls.partial_success(
                all_data,
                all_errors,
                total_attempted=len(results),
                succeeded_count=len(all_data),
            )
        return cls(success=True, data=all_data, errors=all_errors)

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

    def get_errors_by_severity(
        self, severity: ErrorSeverity
    ) -> List[ProcessingError]:
        """Get errors filtered by severity level."""
        return [e for e in self.errors if e.severity == severity]

    def get_errors_by_source(self, source: str) -> List[ProcessingError]:
        """Get errors filtered by source component."""
        return [e for e in self.errors if e.source == source]

    def group_errors_by_source(self) -> Dict[str, List[ProcessingError]]:
        """Group all errors by their source component."""
        grouped: Dict[str, List[ProcessingError]] = {}
        for error in self.errors:
            if error.source not in grouped:
                grouped[error.source] = []
            grouped[error.source].append(error)
        return grouped

    def unwrap(self) -> T:
        """Return data or raise if failed."""
        if not self.success:
            msg = self.errors[0].message if self.errors else "Unknown error"
            exc = self.errors[0].exception if self.errors else None
            if exc:
                raise exc
            raise RuntimeError(msg)
        return self.data  # type: ignore


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


class ProcessingPhase(Enum):
    """Phases of a processing run."""

    INITIALIZATION = "initialization"
    VALIDATION = "validation"
    DATA_FETCH = "data_fetch"
    PROOF_GENERATION = "proof_generation"
    OUTPUT = "output"


@dataclass
class ProcessingReport:
    """
    Comprehensive report of a processing run.

    Tracks every decision, skip, and failure with full context.
    Designed for both programmatic access and human debugging.
    """

    operation: str
    phase: ProcessingPhase = ProcessingPhase.INITIALIZATION

    # Processing counts
    total_items: int = 0
    processed_items: int = 0
    skipped_items: int = 0
    failed_items: int = 0
    degraded_items: int = 0

    # Detailed tracking
    errors: List[ProcessingError] = field(default_factory=list)
    warnings: List[ProcessingError] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)
    failed: List[Dict[str, Any]] = field(default_factory=list)
    degraded: List[Dict[str, Any]] = field(default_factory=list)

    # For serialization
    _phases_log: List[Dict[str, Any]] = field(default_factory=list)
    _phase_results: Dict[str, "Result"] = field(default_factory=dict)

    def set_phase(self, phase: ProcessingPhase) -> None:
        """Update current processing phase and log it."""
        self.phase = phase
        self._phases_log.append({"phase": phase.value})

    def add_phase_result(self, phase: str, result: "Result") -> None:
        """Add a result for a specific phase."""
        self._phase_results[phase] = result
        if result.success:
            self.processed_items += 1
        else:
            self.failed_items += 1
        self.total_items += 1

    def has_phase(self, phase: str) -> bool:
        """Check if a phase result exists."""
        return phase in self._phase_results

    def get_phase_result(self, phase: str) -> Optional["Result"]:
        """Get the result for a specific phase."""
        return self._phase_results.get(phase)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        total = len(self._phase_results)
        successful = sum(1 for r in self._phase_results.values() if r.success)
        failed = total - successful
        return {
            "total_phases": total,
            "successful_phases": successful,
            "failed_phases": failed,
            "success_rate": successful / total if total > 0 else 1.0,
        }

    def record_skip(
        self,
        item_id: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an intentionally skipped item."""
        self.skipped_items += 1
        self.skipped.append(
            {
                "item_id": item_id,
                "reason": reason,
                "context": context or {},
                "phase": self.phase.value,
            }
        )

    def record_failure(
        self,
        item_id: str,
        error: ProcessingError,
    ) -> None:
        """Record a failed item."""
        self.failed_items += 1
        self.errors.append(error)
        self.failed.append(
            {
                "item_id": item_id,
                "error": error.to_dict(),
                "phase": self.phase.value,
            }
        )

    def record_degraded(
        self,
        item_id: str,
        reason: str,
        missing_data: Optional[List[str]] = None,
    ) -> None:
        """Record an item processed in degraded mode."""
        self.degraded_items += 1
        self.degraded.append(
            {
                "item_id": item_id,
                "reason": reason,
                "missing_data": missing_data or [],
                "phase": self.phase.value,
            }
        )

    def record_success(self) -> None:
        """Record a successfully processed item."""
        self.processed_items += 1

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_items == 0:
            return 1.0
        return self.processed_items / self.total_items

    @property
    def has_failures(self) -> bool:
        """Check if any items failed."""
        return self.failed_items > 0

    @property
    def has_critical_failures(self) -> bool:
        """Check if any critical errors occurred."""
        return any(e.severity == ErrorSeverity.CRITICAL for e in self.errors)

    def to_summary(self) -> Dict[str, Any]:
        """Generate a human-readable summary."""
        return {
            "operation": self.operation,
            "success_rate": f"{self.success_rate:.1%}",
            "processed": self.processed_items,
            "failed": self.failed_items,
            "skipped": self.skipped_items,
            "degraded": self.degraded_items,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "has_critical": self.has_critical_failures,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        phases = {}
        for name, result in self._phase_results.items():
            phases[name] = {
                "success": result.success,
                "data": result.data,
                "errors": [e.to_dict() for e in result.errors],
            }
        return {
            "operation": self.operation,
            "phase": self.phase.value,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "skipped_items": self.skipped_items,
            "failed_items": self.failed_items,
            "degraded_items": self.degraded_items,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [e.to_dict() for e in self.warnings],
            "skipped": self.skipped,
            "failed": self.failed,
            "degraded": self.degraded,
            "phases_log": self._phases_log,
            "phases": phases,
        }


class ValidationSeverity(Enum):
    """What happens when validation fails."""

    BLOCK = "block"  # Stop processing entirely
    SKIP = "skip"  # Skip this item, continue others
    WARN = "warn"  # Log warning, continue with item


@dataclass
class ValidationRule:
    """A single validation rule."""

    name: str
    check: Any  # Callable[[Any], bool]
    severity: ValidationSeverity
    error_message: str


@dataclass
class ValidationResult:
    """Result of running validation gates."""

    passed: bool
    failures: List[Dict[str, Any]] = field(default_factory=list)


class ValidationGate:
    """
    Validation gate that runs a set of rules against input data.

    Gates are checkpoints in the data flow that ensure data
    meets requirements before proceeding.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self.rules: List[ValidationRule] = []

    def add_rule(
        self,
        name: str,
        check: Any,  # Callable
        severity: ValidationSeverity,
        error_message: str,
    ) -> "ValidationGate":
        """Add a validation rule."""
        self.rules.append(
            ValidationRule(
                name=name,
                check=check,
                severity=severity,
                error_message=error_message,
            )
        )
        return self

    def validate_input(self, data: Any) -> Result[Any]:
        """
        Validate input data.

        Performs basic validation on input data:
        - For dataclasses: checks required fields are non-negative integers
        - Returns Result with success/failure
        """
        try:
            # Basic dataclass validation
            if hasattr(data, "__dataclass_fields__"):
                for field_name, field_info in data.__dataclass_fields__.items():
                    value = getattr(data, field_name)
                    # Check for negative integers (common validation)
                    if isinstance(value, int) and value < 0:
                        return Result.fail(
                            ProcessingError(
                                source="validation.input",
                                message=f"Invalid {field_name}: must be non-negative",
                                severity=ErrorSeverity.ERROR,
                                context={"field": field_name, "value": value},
                            )
                        )
            return Result.ok(data)
        except Exception as e:
            return Result.fail(
                ProcessingError(
                    source="validation.input",
                    message=f"Input validation failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    exception=e,
                )
            )

    def validate_output(
        self, data: Any, schema: Optional[str] = None
    ) -> Result[Any]:
        """
        Validate output data against expected schema.

        Args:
            data: Output data to validate
            schema: Schema name for validation (e.g., "campaign_list")
        """
        try:
            if schema == "campaign_list" and isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        if "gauge" not in item:
                            return Result.fail(
                                ProcessingError(
                                    source="validation.output",
                                    message="Missing required field: gauge",
                                    severity=ErrorSeverity.ERROR,
                                    context={"item": item},
                                )
                            )
            return Result.ok(data)
        except Exception as e:
            return Result.fail(
                ProcessingError(
                    source="validation.output",
                    message=f"Output validation failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    exception=e,
                )
            )

    def validate_with_custom(
        self, data: Any, validator: Any  # Callable
    ) -> Result[Any]:
        """
        Validate with a custom validator function.

        FAIL-CLOSED: If the validator raises, the validation fails.
        """
        try:
            result = validator(data)
            if result is False:
                return Result.fail(
                    ProcessingError(
                        source="validation.custom",
                        message="Custom validation failed",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            return Result.ok(data)
        except Exception as e:
            # FAIL-CLOSED: validation error = validation failure
            return Result.fail(
                ProcessingError(
                    source="validation.custom",
                    message=f"Validation error: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    exception=e,
                )
            )

    def validate(
        self, data: Any, context: Optional[Dict[str, Any]] = None
    ) -> Result[Any]:
        """
        Run all validation rules against data.

        Returns:
            Result: Success with data if all blocking rules pass,
                   failure if any blocking rule fails.
        """
        context = context or {}
        errors: List[ProcessingError] = []
        should_block = False

        for rule in self.rules:
            try:
                if not rule.check(data):
                    error = ProcessingError(
                        source=f"validation.{self.name}.{rule.name}",
                        message=rule.error_message,
                        severity=(
                            ErrorSeverity.CRITICAL
                            if rule.severity == ValidationSeverity.BLOCK
                            else ErrorSeverity.WARNING
                            if rule.severity == ValidationSeverity.WARN
                            else ErrorSeverity.ERROR
                        ),
                        context={**context, "rule": rule.name},
                    )
                    errors.append(error)

                    if rule.severity == ValidationSeverity.BLOCK:
                        should_block = True
                    elif rule.severity == ValidationSeverity.SKIP:
                        # For SKIP, we still fail the result but not critically
                        pass

            except Exception as e:
                # Validation rule itself threw
                errors.append(
                    ProcessingError(
                        source=f"validation.{self.name}.{rule.name}",
                        message=f"Validation rule threw: {str(e)}",
                        severity=ErrorSeverity.ERROR,
                        context=context,
                        exception=e,
                    )
                )

        if should_block and errors:
            return Result.fail(errors[0])

        if errors:
            # Non-blocking errors - return partial success
            return Result.partial_success(data, errors)

        return Result.ok(data)
