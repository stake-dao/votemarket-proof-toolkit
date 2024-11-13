## Claiming Campaign Rewards

### Overview

Claiming rewards in VoteMarket V2 follows a similar pattern to V1, but with additional steps due to the cross-chain nature of the system. The process involves submitting storage proofs to verify Ethereum state data on sidechains.

### Storage Proofs

Storage proofs are essential for claiming rewards on sidechains. These proofs can be submitted by anyone and are cryptographically verified against Ethereum block roots.

> [!TIP]
> The [votemarket-proof-toolkit](https://github.com/stake-dao/votemarket-proof-toolkit) provides all necessary tools and documentation for generating these proofs.

### Claim Process

To enable claims for an epoch, follow these steps:

1. **Get Epoch Block Data**
   - Retrieve the L1 block data for the specific epoch from the Oracle
   - This data includes block number, hash, timestamp, and state root
   - For implementation details, see `get_epoch_block_data()` in `claim_rewards.py`

2. **Submit Gauge Controller Proof**
   - Check if a gauge controller proof already exists
   - If not, generate and submit the proof using the VoteMarket Proofs toolkit
   - For implementation, refer to `submit_controller_proof()` in `claim_rewards.py`

3. **Submit Gauge Proof**
   - Verify if the gauge weight proof is already registered
   - If not, generate and submit the proof for the specific gauge and epoch
   - See `submit_gauge_proof()` in `claim_rewards.py` for implementation details

4. **Submit User Vote Proofs**
   - Required only for eligible voters
   - Also need to submit listed (blacklist + whitelist) user proofs, in order for the computation to be done
   - Check if the user's vote proof is already registered
   - If not, generate and submit the proof for the user, gauge, and epoch
   - Refer to `submit_user_proof()` in `claim_rewards.py` for implementation

5. **Execute Claim**
   - Once all proofs are submitted, execute the claim function
   - The claim function signature remains similar to V1:

   ```solidity
   function claim(
       uint256 campaignId,
       address account,
       uint256 epoch,
       bytes calldata hookData
   ) external returns (uint256 claimed)
   ```

### Important Notes

> [!WARNING]
> - Ineligible users cannot claim rewards, regardless of proof submission
> - Ensure all required proofs are submitted for previous epochs before attempting to claim (same as for updating campaigns)
> - The claim process may require multiple transactions if proofs need to be submitted -> can be done in one go with the bundler

> [!TIP]
> For complete implementation details and examples, refer to the `claim_rewards.py` script in the `examples/` directory.