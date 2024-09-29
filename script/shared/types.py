from typing import TypedDict

class Campaign(TypedDict):
    id: int
    chain_id: int
    gauge: str
    manager: str
    reward_token: str
    number_of_periods: int
    max_reward_per_vote: int
    total_reward_amount: int
    total_distributed: int
    start_timestamp: int
    end_timestamp: int
    hook: str