## Campaign Creation

### 1. L1 Token Campaigns (Ethereum → L2)

#### Overview

Creating a campaign with L1 tokens involves several steps to ensure the tokens are properly managed across chains:
1. Locking the original tokens on Ethereum
2. Bridging a message to L2
3. Minting wrapped tokens on L2 to be used for the campaign

The helper contract for creating campaigns is the [CampaignRemoteManager](https://etherscan.io/address/0x53aD4Cd1F1e52DD02aa9FC4A8250A1b74F351CA2).

#### Implementation

> [!WARNING]
> The implementation of L1 token campaigns requires calculating the CCIP fee and creating the campaign. This process is payable due to the CCIP bridge, which is a change from V1.

> [!TIP]
> For detailed steps and code, refer to the `create_campaign_l1.py` script in the `examples/` directory.

### 2. L2 Token Campaigns (Native L2)

#### Overview

For campaigns directly on L2, the process is more straightforward as there is no need to bridge tokens. The rewards are deposited directly on the corresponding L2 VoteMarket.

#### Implementation

> [!TIP]
> To create a campaign directly on L2, follow the steps outlined in the `create_campaign_l2.py` script in the `examples/` directory.
