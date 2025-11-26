"""VoteMarket Toolkit - Python SDK for VoteMarket campaigns and proofs."""

__version__ = "1.0.6"

from .campaigns import CampaignService
from .proofs import VoteMarketProofs as ProofManager
from .shared import registry

__all__ = ["CampaignService", "ProofManager", "registry"]
