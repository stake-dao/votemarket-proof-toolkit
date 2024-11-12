## Campaign Creation

### 1. L1 Token Campaigns (Ethereum → Arbitrum)

#### Overview

> [!IMPORTANT]
> When creating campaigns on Ethereum, ensure you have enough native tokens (ETH) to cover CCIP fees in addition to your reward tokens.

> [!NOTE]
> Creating a campaign with L1 tokens involves several steps to ensure the tokens are properly managed across chains:
> 1. Locking the original tokens on Ethereum
> 2. Bridging a message to Arbitrum
> 3. Minting wrapped tokens on Arbitrum to be used for the campaign

The helper contract for creating campaigns is the [CampaignRemoteManager](https://etherscan.io/address/0xd1f0101Df22Cb7447F486Da5784237AB7a55eB4e).

#### Implementation

> [!WARNING]
> The implementation of L1 token campaigns requires calculating the CCIP fee and creating the campaign. This process is payable due to the CCIP bridge, which is a change from V1.

> [!TIP]
> For detailed steps and code, refer to the `create_campaign_l1.py` script in the `examples/` directory.

### 2. L2 Token Campaigns (Native Arbitrum)

#### Overview

> [!NOTE]
> For campaigns directly on L2, the process is more straightforward as there is no need to bridge tokens. The rewards are deposited directly on the corresponding L2 VoteMarket.

#### Implementation

> [!TIP]
> To create a campaign directly on L2, follow the steps outlined in the `create_campaign_l2.py` script in the `examples/` directory.
