## Campaign Management

### Update Campaign Epoch

#### Overview

Before managing a campaign (extending duration, adding rewards, etc.), its state must be synchronized on-chain. This process requires careful attention to epoch updates and storage proofs.

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

For implementation details, see `update_epoch.py` in the `examples/` directory.

### From L1 (Ethereum)

#### Overview

L1 campaign management is primarily used for increasing rewards in existing campaigns. All other management operations should be performed directly on Arbitrum. This process requires:

1. Calculating CCIP fees for cross-chain message
2. Approving additional tokens (if needed)
3. Executing management transaction with CCIP fees

For detailed implementation, refer to `manage_campaign_l1.py` in the `examples/` directory.

### From L2 (Arbitrum)

#### Overview

L2 campaign management offers more flexibility but has important considerations:

- Can add rewards only for non-wrapped tokens (native L2 tokens)
- For wrapped tokens (L1 tokens bridged to L2):
  - Must have wrapped tokens in wallet from:
    - Previous campaign claims
    - Closed campaigns without L1 bridge back
  - If no wrapped tokens available, use L1 management instead

For implementation details, see `manage_campaign_l2.py` in the `examples/` directory.