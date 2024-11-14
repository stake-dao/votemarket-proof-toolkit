## Campaign Management

### Update Campaign Epoch

#### Overview

Before managing a campaign (extending the duration, adding rewards, etc.), its state must be synchronized with Layer 1 (L1) data on each epoch. This process requires careful attention to epoch updates and the corresponding storage proofs on the L1 state.

```solidity
function updateEpoch(
    uint256 campaignId,  // ID of the campaign
    uint256 epoch,       // Epoch to update
    bytes calldata hookData  // Additional data for hooks (if any)
)
```

#### Important Notes

1. **Sequential Updates Required**
   - Updates must be performed in chronological order
   - Example: If last update was epoch 100 and current is 103, must update 100 → 101 → 102 → 103

2. **Valid Epochs**
   - Must align with `EPOCH_LENGTH`
   - Cannot update future epochs
   - Must start from campaign's start timestamp

3. **Storage Proofs**
   - Each epoch update requires valid gauge vote proofs
   - Proofs must be inserted before updating epochs
   - See [Storage Proofs](./storage_proofs.md) section for details

#### Common Errors
- `EPOCH_NOT_VALID`: Epoch not correct/missing for that campaign
- `STATE_MISSING`: Missing storage proofs

> [!TIP]
> For implementation details on proofs, as it is also required for claiming rewards, see `claim_rewards.py` in the `examples/` directory.

### From L1 (Ethereum)

#### Overview

L1 campaign management is primarily used for increasing rewards in existing campaigns. All other management operations should be performed directly on Arbitrum.

This process requires:

1. Calculating CCIP fees for cross-chain message
2. Approving additional tokens (if needed)
3. Executing management transaction with CCIP fees

> [!TIP]
> For detailed implementation, refer to `manage_campaign_l1.py` in the `examples/` directory.

### From L2 (Arbitrum)

#### Overview

> [!WARNING]
> Campaign management on L2 has the following restrictions for adding rewards:
> - Native L2 tokens: Can be added directly on L2
> - Wrapped tokens (L1 tokens on L2): Must be added through L1
>   - Exception: You can use L2 if you already have wrapped tokens from previous claims or closed campaigns

> [!TIP]
> For implementation details, see `manage_campaign_l2.py` in the `examples/` directory.