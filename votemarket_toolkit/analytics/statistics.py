"""Statistical utilities for robust campaign analysis."""

from typing import List


def percentile(values: List[float], q: float) -> float:
    """
    Calculate percentile of values.

    Args:
        values: List of numeric values
        q: Percentile (0.0 to 1.0, e.g. 0.70 for 70th percentile)

    Returns:
        Percentile value, or 0.0 if empty
    """
    if not values:
        return 0.0

    sorted_values = sorted(v for v in values if v > 0)
    if not sorted_values:
        return 0.0

    idx = int(q * (len(sorted_values) - 1))
    return sorted_values[idx]


def ema_series(values: List[float], alpha: float = 0.3) -> float:
    """
    Calculate exponential moving average over series.

    Args:
        values: List of values (ordered, oldest to newest)
        alpha: Smoothing factor (0 to 1, higher = more weight to recent)

    Returns:
        Final EMA value
    """
    if not values:
        return 0.0

    clean_values = [v for v in values if v > 0]
    if not clean_values:
        return 0.0

    # Start with first value
    result = clean_values[0]

    # Update with each subsequent value
    for val in clean_values[1:]:
        result = alpha * val + (1 - alpha) * result

    return result


def mad(values: List[float]) -> float:
    """
    Calculate Median Absolute Deviation (robust variability measure).

    Args:
        values: List of numeric values

    Returns:
        MAD value, or 0.0 if empty
    """
    if not values:
        return 0.0

    clean_values = [v for v in values if v > 0]
    if not clean_values:
        return 0.0

    # Find median (middle value)
    median = percentile(clean_values, 0.5)

    # Calculate absolute deviations from median
    deviations = [abs(v - median) for v in clean_values]

    # Return median of deviations
    return percentile(deviations, 0.5)


def clamp(value: float, min_value: float, max_value: float) -> float:
    """
    Clamp value between min and max bounds.

    Args:
        value: Value to clamp
        min_value: Minimum allowed
        max_value: Maximum allowed

    Returns:
        Clamped value
    """
    return max(min_value, min(value, max_value))


def safe_divide(
    numerator: float, denominator: float, default: float = 0.0
) -> float:
    """
    Safe division with zero protection.

    Args:
        numerator: Numerator
        denominator: Denominator
        default: Default value if denominator is zero

    Returns:
        Result of division or default
    """
    if abs(denominator) < 1e-9:
        return default
    return numerator / denominator
