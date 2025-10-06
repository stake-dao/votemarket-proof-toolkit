"""Data module for VoteMarket toolkit - handles eligibility and oracle queries."""

from .eligibility import EligibilityService
from .oracle import OracleService

__all__ = ["EligibilityService", "OracleService"]
