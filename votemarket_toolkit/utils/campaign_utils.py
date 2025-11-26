"""Campaign-specific utilities for closability and status calculations."""

from datetime import datetime, timedelta
from typing import Any, Dict

# Constants for closability calculation
CLAIM_DEADLINE_MONTHS = 6  # 6 months claim period
CLOSE_WINDOW_MONTHS = 1  # 1 month close window after claim period
TOTAL_MONTHS = CLAIM_DEADLINE_MONTHS + CLOSE_WINDOW_MONTHS  # 7 months total


def calculate_deadlines(end_timestamp: int) -> Dict[str, Any]:
    """Calculate the claim deadline and close window timestamps."""
    end_date = datetime.fromtimestamp(end_timestamp)

    # Calculate 6 months after end (start of close window)
    claim_deadline = end_date + timedelta(days=30 * CLAIM_DEADLINE_MONTHS)

    # Calculate 7 months after end (end of close window)
    close_window_end = end_date + timedelta(days=30 * TOTAL_MONTHS)

    current_time = datetime.now()

    return {
        "end_date": end_date,
        "claim_deadline": claim_deadline,
        "close_window_end": close_window_end,
        "current_time": current_time,
        "is_within_close_window": claim_deadline
        <= current_time
        < close_window_end,
        "is_after_close_window": current_time >= close_window_end,
        "days_since_end": (current_time - end_date).days,
        "days_since_claim_deadline": (
            (current_time - claim_deadline).days
            if current_time >= claim_deadline
            else 0
        ),
        "days_until_anyone_can_close": (
            (close_window_end - current_time).days
            if claim_deadline <= current_time < close_window_end
            else 0
        ),
    }


def get_closability_info(campaign: dict) -> Dict[str, Any]:
    """
    Determine if campaign is closable and by whom.
    Returns dict with closability information.
    """
    current_timestamp = int(datetime.now().timestamp())
    end_timestamp = campaign["campaign"]["end_timestamp"]

    closability = {
        "is_closable": False,
        "can_be_closed_by": None,
        "funds_go_to": None,
        "days_until_closable": None,
        "closability_status": None,
    }

    # If campaign is already closed
    if campaign["is_closed"]:
        closability["closability_status"] = "Already Closed"
        return closability

    # If campaign hasn't ended yet
    if end_timestamp >= current_timestamp:
        days_until_end = (end_timestamp - current_timestamp) // 86400
        closability["closability_status"] = f"Active ({days_until_end}d left)"
        return closability

    # Calculate deadlines
    deadlines = calculate_deadlines(end_timestamp)

    # If within 6 months of end (claim period)
    if deadlines["days_since_end"] < (CLAIM_DEADLINE_MONTHS * 30):
        days_until_closable = (CLAIM_DEADLINE_MONTHS * 30) - deadlines[
            "days_since_end"
        ]
        closability["closability_status"] = (
            f"Claim Period ({days_until_closable}d until closable)"
        )
        closability["days_until_closable"] = days_until_closable
        return closability

    # If within close window (6-7 months after end)
    if deadlines["is_within_close_window"]:
        closability["is_closable"] = True
        closability["can_be_closed_by"] = "Manager Only"
        closability["funds_go_to"] = "Manager"
        closability["closability_status"] = (
            f"Closable by Manager ({deadlines['days_until_anyone_can_close']}d until anyone)"
        )
        return closability

    # If after close window (>7 months after end)
    if deadlines["is_after_close_window"]:
        closability["is_closable"] = True
        closability["can_be_closed_by"] = "Anyone"
        closability["funds_go_to"] = "Fee Collector"
        days_past_window = deadlines["days_since_claim_deadline"] - 30
        closability["closability_status"] = (
            f"Closable by Anyone ({days_past_window}d overdue)"
        )
        return closability

    return closability


def get_campaign_status(campaign: dict) -> str:
    """
    Determine campaign status based on its state.
    Returns colored status string for rich console.
    """
    current_timestamp = int(datetime.now().timestamp())

    if campaign["is_closed"]:
        return "[red]Closed[/red]"
    elif campaign["campaign"]["end_timestamp"] < current_timestamp:
        return "[orange3]Inactive[/orange3]"  # Past end time but not closed
    else:
        return "[green]Active[/green]"
