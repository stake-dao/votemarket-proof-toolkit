# VoteMarket V2 Integration Guide

This guide is designed to help developers integrate and migrate their applications to the new VoteMarket V2 architecture. The new version introduces some changes in interaction with the platform, due to native cross-chain operations.

## Contents

- [VoteMarket V2 Integration Guide](#votemarket-v2-integration-guide)
  - [Contents](#contents)
  - [Quick Reference](#quick-reference)
    - [Contract Addresses \& Deployments](#contract-addresses--deployments)
  - [Campaign Creation](#campaign-creation)
  - [Campaign Management](#campaign-management)
  - [Campaign Closing](#campaign-closing)
  - [Claiming Campaign Rewards](#claiming-campaign-rewards)
  - [Using the Bundler for Batch Operations](#using-the-bundler-for-batch-operations)
    - [Proof Submissions](#proof-submissions)
    - [Claims](#claims)
      - [Update Epochs](#update-epochs)

## Quick Reference

### Contract Addresses & Deployments
Find all supported protocols, contract addresses, and learn how Votemarket V2 works in our [GitHub repository](https://github.com/stake-dao/votemarket-v2).

## Campaign Creation

> [!NOTE]
> VoteMarket V2 introduces a new cross-chain campaign creation flow. Below is a comparison between V1 and V2:

<table>
<tr>
<th>VoteMarket V1</th>
<th>VoteMarket V2</th>
</tr>
<tr>
<td>
<img src="../assets/votemarket_v1_creation.png" alt="VoteMarket V1 Campaign Creation" width="400"/>
</td>
<td>
<img src="../assets/votemarket_v2_creation.png" alt="VoteMarket V2 Campaign Creation" width="400"/>
</td>
</tr>
</table>

Key differences in V2:

- **msg.value** is required to cover *CCIP cross-chain messaging fees*
- **Different function signature** with additional parameters:
  - *Gas limit* for CCIP execution on L2/destination chain 
  - *Hook address* for custom logic integration

For detailed implementation:
- [L1 Token Campaigns (Ethereum → L2)](guides/campaign_creation.md#l1-token-campaigns-ethereum)
- [L2 Token Campaigns (Directly on L2)](guides/campaign_creation.md#l2-token-campaigns-native-l2)

## Campaign Management

- [Update Campaign Epoch](guides/campaign_management.md#update-campaign-epoch)
- [From L1](guides/campaign_management.md#from-l1)
- [From L2](guides/campaign_management.md#from-l2)

## Campaign Closing

- [Overview](guides/campaign_closing.md#campaign-closing)

## Claiming Campaign Rewards

- [Storage Proofs](guides/claiming_rewards.md#storage-proofs)

## Using the Bundler for Batch Operations

The Bundler contract (`0x67346f8b9B7dDA4639600C190DDaEcDc654359c8`) provides multicall functionality to batch multiple operations in a single transaction. This is particularly useful for:

### Proof Submissions
Batch multiple proof submissions together:
- `setBlockData`
- `setPointData`
- `setAccountData`

### Claims
- Submit multiple claims in a single transaction
- Combine proof submissions with claims

#### Update Epochs
- Update multiple epochs in a single transaction
- Combine proof submissions with epoch updates

> [!TIP]
> An usage of the bundler is present in the `claim_rewards.py` script in the `examples/` directory.