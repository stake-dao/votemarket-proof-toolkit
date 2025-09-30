"""
Simple statistical helpers for campaign optimization.

Why these methods?
- percentile: Find "typical" market value, ignoring extreme outliers
- ema_series: Smooth historical data, giving more weight to recent values
- mad: Measure "spread" of data for safety margins
- clamp: Enforce min/max bounds
- safe_divide: Avoid division by zero errors
"""

from typing import List


def percentile(values: List[float], q: float) -> float:
    """
    Find the value where q% of data is below it.

    Example: If you have [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    - percentile(0.50) = 5  (median, 50% below)
    - percentile(0.70) = 7  (70% of values are below 7)

    Why use this? More robust than average - not skewed by extreme values.
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
    Exponential Moving Average - weighted average favoring recent values.

    Example: If you have votes = [1000, 1100, 1200, 1300, 1400]
    - Simple average = 1200
    - EMA (alpha=0.3) ≈ 1250 (gives more weight to recent 1300, 1400)

    Why use this? Smooths out noise while adapting to trends.
    alpha=0.3 means: new value gets 30% weight, history gets 70%
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
    Median Absolute Deviation - measure of "spread" in data.

    Example: If you have $/vote = [0.001, 0.002, 0.003, 0.100]
    - Standard deviation would be inflated by the 0.100 outlier
    - MAD ignores outliers and gives a robust measure of spread

    Why use this? We use MAD as a safety margin:
    target = percentile(0.70) + 0.5 * MAD
    This gives us breathing room above typical market rates.
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
    Enforce minimum and maximum bounds.

    Example: clamp(150, min=0, max=100) = 100
             clamp(-5, min=0, max=100) = 0
             clamp(50, min=0, max=100) = 50

    Why use this? Ensures calculated targets stay within sensible limits.
    """
    return max(min_value, min(value, max_value))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Division that never crashes on zero.

    Example: safe_divide(10, 2) = 5.0
             safe_divide(10, 0) = 0.0 (default)

    Why use this? Prevents crashes when vote counts or prices are missing.
    """
    if abs(denominator) < 1e-9:  # Essentially zero
        return default
    return numerator / denominator