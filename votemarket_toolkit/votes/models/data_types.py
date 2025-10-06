from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class VoteLog:
    time: int
    user: str
    gauge_addr: str
    weight: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoteLog":
        return cls(
            time=data["time"],
            user=data["user"],
            gauge_addr=data["gauge_addr"],
            weight=data["weight"],
        )


@dataclass
class GaugeVotes:
    gauge_address: str
    votes: List[VoteLog]
    latest_block: int
