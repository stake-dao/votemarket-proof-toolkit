# Statistics Methods Explained

## Why These Methods?

Traditional approaches use **averages** and **standard deviation**, but these are easily skewed by outliers. For example, if most campaigns offer $0.001/vote but one outlier offers $0.10/vote, the average would be inflated.

We use **robust statistics** that ignore outliers and focus on typical values.

---

## Methods Used

### 1. Percentile (instead of Average)

**What it does:** Finds the value where X% of data is below it.

**Example:**
- If $/vote values are: [0.001, 0.002, 0.003, 0.004, 0.100]
- Average = 0.022 (inflated by the 0.100 outlier)
- 70th percentile = 0.004 (typical value, ignoring outlier)

**Why 70th percentile?**
- Not too aggressive (like 90th)
- Not too conservative (like 50th/median)
- Good balance: competitive but not extreme

**Code:**
```python
market_target = percentile(peer_campaigns, 0.70)  # 70th percentile
```

---

### 2. EMA - Exponential Moving Average (instead of Simple Average)

**What it does:** Calculates weighted average that favors recent values.

**Example:**
- Votes over 5 weeks: [1000, 1100, 1200, 1300, 1400]
- Simple average = 1200
- EMA (alpha=0.3) ≈ 1250 (more weight to recent 1300, 1400)

**Why use it?**
- Smooths out noise
- Adapts to trends
- Recent data is more relevant

**Formula:** `new_ema = alpha * new_value + (1 - alpha) * old_ema`

**Code:**
```python
votes_expected = ema_series([1000, 1100, 1200, 1300, 1400], alpha=0.3)
# Result: gives more weight to 1300 and 1400
```

---

### 3. MAD - Median Absolute Deviation (instead of Standard Deviation)

**What it does:** Measures "spread" of data, ignoring outliers.

**Example:**
- $/vote values: [0.001, 0.002, 0.003, 0.100]
- Standard deviation ≈ 0.043 (inflated by outlier)
- MAD ≈ 0.001 (robust measure of typical spread)

**Why use it?**
- Provides safety margin above target
- Not skewed by extreme values

**Formula:**
1. Find median of values
2. Calculate absolute deviations from median
3. Take median of those deviations

**Code:**
```python
market_mad = mad(peer_campaigns)
target = percentile(peers, 0.70) + 0.5 * market_mad  # Add safety margin
```

---

### 4. Clamp (Enforce Bounds)

**What it does:** Keeps values within min/max limits.

**Example:**
```python
clamp(150, min=0, max=100) = 100
clamp(-5, min=0, max=100) = 0
clamp(50, min=0, max=100) = 50
```

**Why use it?**
- Prevents absurd values
- Enforces policy limits (e.g., never pay more than $1/vote)

---

### 5. Safe Divide (Avoid Crashes)

**What it does:** Division that never crashes on zero.

**Example:**
```python
safe_divide(10, 2) = 5.0
safe_divide(10, 0) = 0.0  # Returns default instead of crashing
```

**Why use it?**
- Prevents crashes when vote counts or prices are missing
- Graceful handling of edge cases

---

## The Full Formula

```python
# Step 1: Get typical market rate (70th percentile)
market_p = percentile(peer_campaigns, 0.70)

# Step 2: Calculate spread (MAD)
market_mad = mad(peer_campaigns)

# Step 3: Add safety margin (0.5 * MAD)
target_raw = market_p + 0.5 * market_mad

# Step 4: Apply bounds
target = clamp(target_raw, min=0.0001, max=1.0)
```

**Result:** A robust target $/vote that is:
- Competitive (70th percentile)
- Safe (has margin for market shifts)
- Bounded (won't be absurd)
- Not skewed by outliers

---

## Visual Example

```
Market $/vote values: [0.001, 0.001, 0.002, 0.002, 0.003, 0.003, 0.004, 0.100]
                                                                ↑            ↑
                                                       70th percentile   outlier

Average:          0.0145  (skewed high by outlier)
70th Percentile:  0.003   (typical competitive value)
MAD:              0.001   (typical spread)

Final target:     0.003 + 0.5*0.001 = 0.0035  ✓ Robust!
```

---

## Summary

| Method | Traditional | Robust | Why Robust is Better |
|--------|-------------|--------|---------------------|
| Central value | Average | Percentile (70th) | Not skewed by outliers |
| Smoothing | Simple average | EMA | Adapts to trends |
| Variability | Std deviation | MAD | Ignores extreme values |
| Safety margin | ±2σ | +0.5*MAD | More stable |

**Bottom line:** These methods give you a competitive, safe target that won't be thrown off by a few extreme campaigns.